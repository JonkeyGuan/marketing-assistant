import React from 'react';

interface Step {
  id: string;
  name: string;
  description: string;
}

interface WorkflowNavigatorProps {
  steps: Step[];
  currentStep: number;
}

export default function WorkflowNavigator({ steps, currentStep }: WorkflowNavigatorProps) {
  return (
    <nav aria-label="Progress" className="mb-8 pb-6">
      <ol className="flex items-center">
        {steps.map((step, index) => (
          <li key={step.id} className={`relative ${index !== steps.length - 1 ? 'pr-8 sm:pr-20 flex-1' : ''}`}>
            {index < currentStep ? (
              <>
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="h-0.5 w-full bg-primary"></div>
                </div>
                <div className="relative flex h-8 w-8 items-center justify-center rounded-full bg-primary">
                  <svg className="h-5 w-5 text-secondary" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                </div>
              </>
            ) : index === currentStep ? (
              <>
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="h-0.5 w-full bg-gray-200"></div>
                </div>
                <div className="relative flex h-8 w-8 items-center justify-center rounded-full border-2 border-primary bg-white">
                  <span className="h-2.5 w-2.5 rounded-full bg-primary"></span>
                </div>
              </>
            ) : (
              <>
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="h-0.5 w-full bg-gray-200"></div>
                </div>
                <div className="relative flex h-8 w-8 items-center justify-center rounded-full border-2 border-gray-300 bg-white">
                  <span className="h-2.5 w-2.5 rounded-full bg-transparent"></span>
                </div>
              </>
            )}

            <div className="hidden sm:block absolute top-10 left-1/2 -translate-x-1/2 text-center w-24">
              <span className={`text-xs font-medium ${index <= currentStep ? 'text-primary' : 'text-gray-500'}`}>
                {step.name}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </nav>
  );
}
