import { isApiMode } from "./runtimeConfig";

export function isDemoMode() {
  if (isApiMode()) return false;
  return import.meta.env.VITE_DEMO_MODE !== "false";
}
