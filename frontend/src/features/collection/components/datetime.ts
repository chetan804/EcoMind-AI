/** `datetime-local` input value (no zone, the viewer's local time) to the ISO instant the API expects. */
export const toIsoFromLocal = (value: string): string => new Date(value).toISOString();
