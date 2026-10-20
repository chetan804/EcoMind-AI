/** Public interface of the waste-classification feature. */
export { ClassificationPage } from './pages/ClassificationPage';
export { createPrediction, uploadImage } from './api/classification-api';
export type { Prediction } from './api/schemas';
