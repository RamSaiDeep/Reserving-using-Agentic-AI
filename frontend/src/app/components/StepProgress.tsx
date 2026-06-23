'use client';
import React from 'react';

interface StepProgressProps {
  currentStep: number;
  steps: string[];
  onStepClick?: (stepIndex: number) => void;
  isStepClickable?: (stepIndex: number) => boolean;
}

export default function StepProgress({
  currentStep,
  steps,
  onStepClick,
  isStepClickable,
}: StepProgressProps) {
  return (
    <div className="flex items-center justify-center flex-1">
      {steps.map((label, i) => {
        const isDone = i < currentStep;
        const isActive = i === currentStep;
        const clickable = isStepClickable ? isStepClickable(i) : false;

        const handleClick = () => {
          if (clickable && onStepClick) {
            onStepClick(i);
          }
        };

        return (
          <React.Fragment key={label}>
            <div
              onClick={handleClick}
              className={`flex items-center gap-1.5 text-[11px] font-medium whitespace-nowrap transition-colors duration-200 ${
                clickable ? 'cursor-pointer hover:text-accent' : 'cursor-default'
              } ${
                isDone ? 'text-accent-green' : isActive ? 'text-text-main' : 'text-text-muted'
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border transition-all duration-200 ${
                  clickable && !isActive ? 'hover:border-accent hover:text-accent' : ''
                } ${
                  isDone
                    ? 'border-accent-green bg-accent-green/10 text-accent-green'
                    : isActive
                    ? 'border-accent bg-accent-dim text-accent font-bold'
                    : 'border-text-muted bg-bg-1 text-text-muted'
                }`}
              >
                {isDone ? '✓' : i + 1}
              </div>
              <span>{label}</span>
            </div>

            {i < steps.length - 1 && (
              <div
                className={`w-7 h-[1px] mx-1.5 flex-shrink-0 transition-colors duration-200 ${
                  isDone ? 'bg-accent-green' : 'bg-border'
                }`}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
