import { get, post } from '@modoor/hooks'

export type Vehicle = {
  id: string
  plate_no: string
  model?: string | null
  status: string
  created_at?: string | null
}

export function listVehicles() {
  return get<{ items: Vehicle[] }>('/api/fleet/vehicles')
}

export function addVehicle(body: { plate_no: string; model?: string }) {
  return post<{ ok: boolean; item: Vehicle }>('/api/fleet/vehicles', body)
}
