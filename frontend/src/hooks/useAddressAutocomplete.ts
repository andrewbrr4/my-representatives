import { useState, useRef, useCallback, useEffect } from "react";

interface PlaceSuggestion {
  mainText: string;
  secondaryText: string;
  fullText: string;
}

const PLACES_API_URL = "https://places.googleapis.com/v1/places:autocomplete";
const DEBOUNCE_MS = 300;
const MIN_CHARS = 3;

export function useAddressAutocomplete() {
  const [suggestions, setSuggestions] = useState<PlaceSuggestion[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      abortRef.current?.abort();
    };
  }, []);

  // Build-time constant — listed in dependency array for correctness
  const apiKey = import.meta.env.VITE_GOOGLE_PLACES_API_KEY;
  console.log("[autocomplete] apiKey present:", !!apiKey, "value prefix:", apiKey?.substring(0, 8));

  const fetchSuggestions = useCallback(
    async (input: string) => {
      console.log("[autocomplete] fetchSuggestions called:", input, "apiKey:", !!apiKey);
      if (!apiKey || input.length < MIN_CHARS) {
        console.log("[autocomplete] bailing: apiKey=", !!apiKey, "length=", input.length);
        setSuggestions([]);
        setIsOpen(false);
        return;
      }

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const resp = await fetch(PLACES_API_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": apiKey,
          },
          body: JSON.stringify({
            input,
            includedRegionCodes: ["us"],
            includedPrimaryTypes: [
              "street_address",
              "subpremise",
              "route",
              "locality",
            ],
          }),
          signal: controller.signal,
        });

        if (!resp.ok) {
          setSuggestions([]);
          setIsOpen(false);
          return;
        }

        const data = await resp.json();
        const results: PlaceSuggestion[] = (data.suggestions ?? [])
          .filter(
            (s: Record<string, unknown>) => {
              const pred = s.placePrediction as { structuredFormat?: unknown } | undefined;
              return pred !== undefined && pred.structuredFormat !== undefined;
            }
          )
          .map(
            (s: {
              placePrediction: {
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
            })
          );

        setSuggestions(results);
        setIsOpen(results.length > 0);
      } catch (err) {
        // Aborted requests (from new keystrokes) should not clear state
        if (err instanceof DOMException && err.name === "AbortError") return;
        setSuggestions([]);
        setIsOpen(false);
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
      console.log("[autocomplete] scheduling fetch for:", value);
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

  return { suggestions, isOpen, onInputChange, close, clear };
}
