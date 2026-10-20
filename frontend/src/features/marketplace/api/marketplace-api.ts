import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { decimal, pageOf, uuid } from '@/services/schemas';

export const CATEGORIES = ['plastics', 'metals', 'paper', 'glass', 'e_waste', 'organics', 'textiles', 'wood', 'furniture', 'other'] as const;
export const UNITS = ['kg', 'units'] as const;
export const CONDITIONS = ['like_new', 'good', 'fair', 'damaged'] as const;
export const LISTING_STATUSES = ['draft', 'published', 'reserved', 'closed'] as const;
export const REQUEST_STATUSES = ['pending', 'accepted', 'declined', 'withdrawn'] as const;

export const listingSchema = z.object({
  id: uuid,
  title: z.string(),
  description: z.string().nullable(),
  category: z.enum(CATEGORIES),
  quantity: decimal,
  unit: z.enum(UNITS),
  condition: z.enum(CONDITIONS),
  facility_id: uuid.nullable(),
  facility_name: z.string().nullable(),
  pickup_city: z.string().nullable(),
  status: z.enum(LISTING_STATUSES),
  owner_id: uuid,
  owner_name: z.string(),
  is_mine: z.boolean(),
  pending_request_count: z.number().int().nullable(),
  my_request_status: z.enum(REQUEST_STATUSES).nullable(),
  published_at: z.string().nullable(),
  closed_at: z.string().nullable(),
  close_reason: z.string().nullable(),
  created_at: z.string(),
});
export type Listing = z.infer<typeof listingSchema>;

export const requestSchema = z.object({
  id: uuid,
  listing_id: uuid,
  listing_title: z.string(),
  requester_id: uuid,
  requester_name: z.string(),
  requester_email: z.string().nullable(),
  message: z.string().nullable(),
  status: z.enum(REQUEST_STATUSES),
  created_at: z.string(),
  decided_at: z.string().nullable(),
});
export type ListingRequest = z.infer<typeof requestSchema>;

export interface ListingFilters {
  page: number;
  q: string;
  category: string;
  mine: boolean;
}

export const fetchListings = (f: ListingFilters, signal?: AbortSignal) =>
  getJson('/marketplace/listings', pageOf(listingSchema), { page_size: 12, sort_by: 'created_at', order: 'desc', ...f }, signal);
export const fetchListing = (id: string, signal?: AbortSignal) => getJson(`/marketplace/listings/${id}`, listingSchema, undefined, signal);
export const createListing = (body: Record<string, unknown>) => sendJson('POST', '/marketplace/listings', listingSchema, body);
export const updateListing = (id: string, body: Record<string, unknown>) => sendJson('PATCH', `/marketplace/listings/${id}`, listingSchema, body);
export const publishListing = (id: string) => sendJson('POST', `/marketplace/listings/${id}/publish`, listingSchema);
export const closeListing = (id: string, reason?: string) => sendJson('POST', `/marketplace/listings/${id}/close`, listingSchema, { reason });

export const fetchListingRequests = (id: string, signal?: AbortSignal) => getJson(`/marketplace/listings/${id}/requests`, z.array(requestSchema), undefined, signal);
export const fetchMyRequests = (signal?: AbortSignal) => getJson('/marketplace/requests/mine', pageOf(requestSchema), { page_size: 50 }, signal);
export const createRequest = (listingId: string, message?: string) => sendJson('POST', `/marketplace/listings/${listingId}/requests`, requestSchema, { message });
export const decideRequest = (id: string, action: 'accept' | 'decline' | 'withdraw') => sendJson('POST', `/marketplace/requests/${id}/${action}`, requestSchema);
