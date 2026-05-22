# OpenShift AI installation

## Prerequisites

### Nvidia GPU

- Node Feature Discovery Operator
- NVIDIA GPU Operator
- L40S x 3 (g6e.12xlarge)

### OpenShift AI

- cert-manager Operator for Red Hat OpenShift
- Authorino Operator
- Red Hat OpenShift Service Mesh **3**
- Red Hat Connectivity Link
- Leader Worker Set Operator
- Red Hat OpenShift AI - **3.x**

## DataScienceCluster

```
apiVersion: datasciencecluster.opendatahub.io/v2
kind: DataScienceCluster
metadata:
  name: default-dsc
  labels:
    app.kubernetes.io/name: datasciencecluster
spec:
  components:
    sparkoperator:
      managementState: Removed
    kserve:
      managementState: Managed
      modelsAsService:
        managementState: Removed
      nim:
        airGapped: false
        managementState: Managed
      rawDeploymentServiceConfig: Headless
      wva:
        managementState: Removed
    modelregistry:
      managementState: Managed
      registriesNamespace: rhoai-model-registries
    feastoperator:
      managementState: Managed
    trustyai:
      eval:
        lmeval:
          permitCodeExecution: deny
          permitOnline: deny
      managementState: Managed
      mcpGuardrailsMode: false
    aipipelines:
      argoWorkflowsControllers:
        managementState: Managed
      managementState: Managed
    ray:
      managementState: Managed
    kueue:
      defaultClusterQueueName: default
      defaultLocalQueueName: default
      managementState: Removed
    workbenches:
      managementState: Managed
      workbenchNamespace: rhods-notebooks
    mlflowoperator:
      managementState: Managed
    dashboard:
      managementState: Managed
    trainer:
      managementState: Managed
    llamastackoperator:
      managementState: Removed
    trainingoperator:
      managementState: Removed
```