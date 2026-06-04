import { useEffect, useState } from "react";

export function useLocalStorageFlag(key, initial) {
  const [value, setValue] = useState(() => localStorage.getItem(key) === null ? initial : localStorage.getItem(key) === "1");
  useEffect(() => localStorage.setItem(key, value ? "1" : "0"), [key, value]);
  return [value, setValue];
}

export function readStoredFlag(key) {
  const value = localStorage.getItem(key);
  if (value === null) return null;
  return value === "1" || value === "true";
}
