import { get, post } from '@modoor/hooks'

export type Shipment = {
  id: string
  ref_no: string
  origin: string
  destination: string
  status: string
  created_at?: string | null
}

export function listShipments() {
  return get<{ items: Shipment[] }>('/api/transport/shipments')
}

export function addShipment(body: {
  ref_no: string
  origin: string
  destination: string
}) {
  return post<{ ok: boolean; item: Shipment }>('/api/transport/shipments', body)
}
