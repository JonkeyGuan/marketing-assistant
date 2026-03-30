"""
Core skill: Deploy marketing campaign HTML to OpenShift via Kubernetes API.
"""
import base64
import io
import logging
from typing import Dict, Optional

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from app.settings import settings

logger = logging.getLogger(__name__)


def get_k8s_clients():
    """Get Kubernetes API clients, using in-cluster config if available."""
    try:
        config.load_incluster_config()
        logger.info("Using in-cluster configuration")
    except config.ConfigException:
        try:
            config.load_kube_config()
            logger.info("Using kubeconfig")
        except config.ConfigException:
            logger.warning("No Kubernetes configuration found")
            return None, None, None

    conf = client.Configuration.get_default_copy()
    conf.verify_ssl = False
    conf.proxy = None
    client.Configuration.set_default(conf)

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    core_v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()
    custom_api = client.CustomObjectsApi()

    return core_v1, apps_v1, custom_api


def sanitize_name(name: str) -> str:
    """Convert a string to a valid Kubernetes resource name."""
    sanitized = name.lower().replace(" ", "-").replace("_", "-")
    sanitized = "".join(c for c in sanitized if c.isalnum() or c == "-")
    while "--" in sanitized:
        sanitized = sanitized.replace("--", "-")
    sanitized = sanitized.strip("-")
    return sanitized[:63]


def ensure_namespace_exists(core_v1: client.CoreV1Api, namespace: str) -> bool:
    """Ensure the target namespace exists."""
    try:
        core_v1.read_namespace(namespace)
        return True
    except ApiException as e:
        if e.status == 404:
            try:
                ns = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
                core_v1.create_namespace(ns)
                logger.info("Created namespace: %s", namespace)
                return True
            except ApiException as create_error:
                logger.error("Failed to create namespace: %s", create_error)
                return False
        logger.error("Error checking namespace: %s", e)
        return False


def create_configmap_from_html(
    core_v1: client.CoreV1Api,
    name: str,
    namespace: str,
    html_content: str,
) -> bool:
    """Create a ConfigMap containing the HTML content."""
    configmap = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name=name),
        data={"index.html": html_content},
    )

    nginx_config_name = name.replace("-html", "-nginx-conf")
    nginx_config = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name=nginx_config_name),
        data={
            "default.conf": """server {
    listen 8080;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    add_header X-Frame-Options "" always;
    add_header Content-Security-Policy "" always;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
"""
        },
    )

    try:
        try:
            core_v1.delete_namespaced_config_map(nginx_config_name, namespace)
        except ApiException as e:
            if e.status != 404:
                raise
        core_v1.create_namespaced_config_map(namespace, nginx_config)
        logger.info("Created nginx ConfigMap: %s", nginx_config_name)
    except ApiException as e:
        logger.warning("Failed to create nginx config: %s", e)

    try:
        try:
            core_v1.delete_namespaced_config_map(name, namespace)
        except ApiException as e:
            if e.status != 404:
                raise
        core_v1.create_namespaced_config_map(namespace, configmap)
        logger.info("Created ConfigMap: %s", name)
        return True
    except ApiException as e:
        logger.error("Failed to create ConfigMap: %s", e)
        return False


def deploy_nginx_with_html(
    apps_v1: client.AppsV1Api,
    deployment_name: str,
    namespace: str,
    configmap_name: str,
) -> bool:
    """Deploy nginx serving the HTML from ConfigMap."""
    nginx_config_name = configmap_name.replace("-html", "-nginx-conf")

    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name=deployment_name,
            labels={"app": deployment_name, "type": "marketing-campaign"},
        ),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(
                match_labels={"app": deployment_name}
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={"app": deployment_name}
                ),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="nginx",
                            image="registry.ocp.demo135.com:5000/docker/nginxinc/nginx-unprivileged:alpine",
                            ports=[client.V1ContainerPort(container_port=8080)],
                            volume_mounts=[
                                client.V1VolumeMount(
                                    name="html-content",
                                    mount_path="/usr/share/nginx/html",
                                    read_only=True,
                                ),
                                client.V1VolumeMount(
                                    name="nginx-config",
                                    mount_path="/etc/nginx/conf.d",
                                    read_only=True,
                                ),
                            ],
                            resources=client.V1ResourceRequirements(
                                limits={"cpu": "100m", "memory": "128Mi"},
                                requests={"cpu": "50m", "memory": "64Mi"},
                            ),
                        )
                    ],
                    volumes=[
                        client.V1Volume(
                            name="html-content",
                            config_map=client.V1ConfigMapVolumeSource(name=configmap_name),
                        ),
                        client.V1Volume(
                            name="nginx-config",
                            config_map=client.V1ConfigMapVolumeSource(name=nginx_config_name),
                        ),
                    ],
                ),
            ),
        ),
    )

    try:
        try:
            apps_v1.replace_namespaced_deployment(deployment_name, namespace, deployment)
            logger.info("Updated Deployment: %s", deployment_name)
        except ApiException as e:
            if e.status == 404:
                apps_v1.create_namespaced_deployment(namespace, deployment)
                logger.info("Created Deployment: %s", deployment_name)
            else:
                raise
        return True
    except ApiException as e:
        logger.error("Failed to create Deployment: %s", e)
        return False


def create_service(
    core_v1: client.CoreV1Api,
    deployment_name: str,
    namespace: str,
) -> bool:
    """Create a Service for the deployment."""
    service = client.V1Service(
        metadata=client.V1ObjectMeta(name=deployment_name),
        spec=client.V1ServiceSpec(
            selector={"app": deployment_name},
            ports=[client.V1ServicePort(port=8080, target_port=8080)],
            type="ClusterIP",
        ),
    )

    try:
        try:
            core_v1.replace_namespaced_service(deployment_name, namespace, service)
            logger.info("Updated Service: %s", deployment_name)
        except ApiException as e:
            if e.status == 404:
                core_v1.create_namespaced_service(namespace, service)
                logger.info("Created Service: %s", deployment_name)
            else:
                raise
        return True
    except ApiException as e:
        logger.error("Failed to create Service: %s", e)
        return False


def create_route(
    custom_api: client.CustomObjectsApi,
    deployment_name: str,
    namespace: str,
    cluster_domain: str,
) -> Optional[str]:
    """Create an OpenShift Route to expose the service externally."""
    route_host = f"{deployment_name}-{namespace}.{cluster_domain}"

    route = {
        "apiVersion": "route.openshift.io/v1",
        "kind": "Route",
        "metadata": {"name": deployment_name, "namespace": namespace},
        "spec": {
            "host": route_host,
            "to": {"kind": "Service", "name": deployment_name},
            "port": {"targetPort": 8080},
            "tls": {
                "termination": "edge",
                "insecureEdgeTerminationPolicy": "Redirect",
            },
        },
    }

    try:
        try:
            custom_api.delete_namespaced_custom_object(
                group="route.openshift.io",
                version="v1",
                namespace=namespace,
                plural="routes",
                name=deployment_name,
            )
        except ApiException as e:
            if e.status != 404:
                raise
        custom_api.create_namespaced_custom_object(
            group="route.openshift.io",
            version="v1",
            namespace=namespace,
            plural="routes",
            body=route,
        )
        logger.info("Created Route: %s", deployment_name)
        return f"https://{route_host}"
    except ApiException as e:
        logger.error("Failed to create Route: %s", e)
        return None


def generate_qr_code(url: str) -> str:
    """Generate a QR code for the URL and return as base64 data URI."""
    try:
        import qrcode

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        b64_data = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{b64_data}"
    except ImportError:
        logger.warning("qrcode library not installed, skipping QR generation")
        return ""


def deploy_preview(campaign_id: str, generated_html: str) -> Dict:
    """Deploy campaign to dev namespace for preview."""
    core_v1, apps_v1, custom_api = get_k8s_clients()

    if not core_v1:
        raise RuntimeError("Kubernetes client not configured")

    deployment_name = sanitize_name(f"{campaign_id}-preview")
    configmap_name = f"{deployment_name}-html"
    namespace = settings.DEV_NAMESPACE

    logger.info("Deploying preview to namespace: %s", namespace)

    if not ensure_namespace_exists(core_v1, namespace):
        raise RuntimeError(f"Failed to access namespace: {namespace}")

    if not create_configmap_from_html(core_v1, configmap_name, namespace, generated_html):
        raise RuntimeError("Failed to create ConfigMap")

    if not deploy_nginx_with_html(apps_v1, deployment_name, namespace, configmap_name):
        raise RuntimeError("Failed to create Deployment")

    if not create_service(core_v1, deployment_name, namespace):
        raise RuntimeError("Failed to create Service")

    preview_url = create_route(custom_api, deployment_name, namespace, settings.CLUSTER_DOMAIN)
    if not preview_url:
        raise RuntimeError("Failed to create Route")

    qr_code = generate_qr_code(preview_url)

    return {
        "deployment_name": deployment_name,
        "preview_url": preview_url,
        "preview_qr_code": qr_code,
    }


def promote_production(campaign_id: str, generated_html: str) -> Dict:
    """Promote campaign to production namespace."""
    core_v1, apps_v1, custom_api = get_k8s_clients()

    if not core_v1:
        raise RuntimeError("Kubernetes client not configured")

    deployment_name = sanitize_name(f"{campaign_id}")
    configmap_name = f"{deployment_name}-html"
    namespace = settings.PROD_NAMESPACE

    logger.info("Promoting to production namespace: %s", namespace)

    if not ensure_namespace_exists(core_v1, namespace):
        raise RuntimeError(f"Failed to access namespace: {namespace}")

    if not create_configmap_from_html(core_v1, configmap_name, namespace, generated_html):
        raise RuntimeError("Failed to create ConfigMap in production")

    if not deploy_nginx_with_html(apps_v1, deployment_name, namespace, configmap_name):
        raise RuntimeError("Failed to create Deployment in production")

    if not create_service(core_v1, deployment_name, namespace):
        raise RuntimeError("Failed to create Service in production")

    production_url = create_route(custom_api, deployment_name, namespace, settings.CLUSTER_DOMAIN)
    if not production_url:
        raise RuntimeError("Failed to create Route in production")

    return {
        "deployment_name": deployment_name,
        "production_url": production_url,
    }
