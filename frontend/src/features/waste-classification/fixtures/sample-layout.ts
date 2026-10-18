/**
 * LAYOUT PREVIEW ONLY. This is not a model output: no classification model has been trained or
 * run. It exists so the result panel's composition can be reviewed. The UI labels it as a sample.
 */
export const sampleResult = {
  className: 'Plastic',
  fill: 0.72, // visual bar length for the layout; deliberately not shown as a confidence number
} as const;

/** Label set planned for the classifier (not a list of classes any model supports today). */
export const plannedClasses = [
  { id: 'plastic', label: 'Plastic' },
  { id: 'paper', label: 'Paper' },
  { id: 'glass', label: 'Glass' },
  { id: 'metal', label: 'Metal' },
  { id: 'organic', label: 'Organic' },
  { id: 'e-waste', label: 'E-waste' },
] as const;
