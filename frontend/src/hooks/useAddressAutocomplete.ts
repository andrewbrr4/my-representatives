import { useState, useRef, useCallback, useEffect } from "react";
import type { Bbox } from "@/lib/usStates";

interface PlaceSuggestion {
  mainText: string;
  secondaryText: string;
  fullText: string;
  placeId: string;
}

export interface AddressComponents {
  street: string;
  city: string;
  state: string;
  zip: string;
}

const PLACES_AUTOCOMPLETE_URL =
  "https://places.googleapis.com/v1/places:autocomplete";
const PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places/";
const DEBOUNCE_MS = 300;
const MIN_CHARS = 3;

type GoogleAddressComponent = {
  longText?: string;
  shortText?: string;
  types?: string[];
};

function parseAddressComponents(
  components: GoogleAddressComponent[]
): AddressComponents {
  let streetNumber = "";
  let route = "";
  let city = "";
  let state = "";
  let zip = "";

  for (const c of components) {
    const types = c.types ?? [];
    if (types.includes("street_number")) streetNumber = c.longText ?? "";
    else if (types.includes("route")) route = c.longText ?? "";
    else if (types.includes("locality")) city = c.longText ?? "";
    else if (!city && types.includes("postal_town")) city = c.longText ?? "";
    else if (!city && types.includes("sublocality_level_1"))
      city = c.longText ?? "";
    else if (types.includes("administrative_area_level_1"))
      state = c.shortText ?? "";
    else if (types.includes("postal_code")) zip = c.longText ?? "";
  }

  const street = [streetNumber, route].filter(Boolean).join(" ");
  return { street, city, state, zip };
}

export function useAddressAutocomplete(stateBbox?: Bbox) {
  const [suggestions, setSuggestions] = useState<PlaceSuggestion[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const detailsAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      abortRef.current?.abort();
      detailsAbortRef.current?.abort();
    };
  }, []);

  const apiKey = import.meta.env.VITE_GOOGLE_PLACES_API_KEY;

  const fetchSuggestions = useCallback(
    async (input: string) => {
      if (!apiKey || input.length < MIN_CHARS) {
        setSuggestions([]);
        setIsOpen(false);
        return;
      }

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const body: Record<string, unknown> = {
          input,
          includedRegionCodes: ["us"],
          includedPrimaryTypes: ["street_address", "subpremise"],
        };
        if (stateBbox) {
          body.locationRestriction = { rectangle: stateBbox };
        }
        const resp = await fetch(PLACES_AUTOCOMPLETE_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": apiKey,
          },
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        if (!resp.ok) {
          setSuggestions([]);
          setIsOpen(false);
          return;
        }

        const data = await resp.json();
        const results: PlaceSuggestion[] = (data.suggestions ?? [])
          .filter((s: Record<string, unknown>) => {
            const pred = s.placePrediction as
              | { structuredFormat?: unknown; placeId?: unknown }
              | undefined;
            return (
              pred !== undefined &&
              pred.structuredFormat !== undefined &&
              typeof pred.placeId === "string"
            );
          })
          .map(
            (s: {
              placePrediction: {
                placeId: string;
                text: { text: string };
                structuredFormat: {
                  mainText: { text: string };
                  secondaryText: { text: string };
                };
              };
            }) => ({
              mainText: s.placePrediction.structuredFormat.mainText.text,
              secondaryText:
                s.placePrediction.structuredFormat.secondaryText.text,
              fullText: s.placePrediction.text.text,
              placeId: s.placePrediction.placeId,
            })
          );

        setSuggestions(results);
        setIsOpen(results.length > 0);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setSuggestions([]);
        setIsOpen(false);
      }
    },
    [apiKey, stateBbox]
  );

  const fetchPlaceDetails = useCallback(
    async (placeId: string): Promise<AddressComponents | null> => {
      if (!apiKey) return null;
      detailsAbortRef.current?.abort();
      const controller = new AbortController();
      detailsAbortRef.current = controller;
      try {
        const resp = await fetch(`${PLACES_DETAILS_URL}${placeId}`, {
          method: "GET",
          headers: {
            "X-Goog-Api-Key": apiKey,
            "X-Goog-FieldMask": "addressComponents",
          },
          signal: controller.signal,
        });
        if (!resp.ok) return null;
        const data = (await resp.json()) as {
          addressComponents?: GoogleAddressComponent[];
        };
        if (!data.addressComponents) return null;
        return parseAddressComponents(data.addressComponents);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return null;
        return null;
      }
    },
    [apiKey]
  );

  const onInputChange = useCallback(
    (value: string) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (!value || value.length < MIN_CHARS) {
        setSuggestions([]);
        setIsOpen(false);
        return;
      }
      timerRef.current = setTimeout(() => fetchSuggestions(value), DEBOUNCE_MS);
    },
    [fetchSuggestions]
  );

  const close = useCallback(() => {
    setIsOpen(false);
  }, []);

  const clear = useCallback(() => {
    setSuggestions([]);
    setIsOpen(false);
    abortRef.current?.abort();
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  return {
    suggestions,
    isOpen,
    onInputChange,
    fetchPlaceDetails,
    close,
    clear,
  };
}
