import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAddressAutocomplete } from "@/hooks/useAddressAutocomplete";
import { US_STATES } from "@/lib/usStates";

interface AddressSearchProps {
  onSearch: (address: string) => void;
  loading: boolean;
}

const ZIP_REGEX = /^\d{5}(-\d{4})?$/;

export function AddressSearch({ onSearch, loading }: AddressSearchProps) {
  const [street, setStreet] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zip, setZip] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const selectedStateBbox = US_STATES.find((s) => s.code === state)?.bbox;
  const { suggestions, isOpen, onInputChange, fetchPlaceDetails, close, clear } =
    useAddressAutocomplete(selectedStateBbox);
  const streetWrapperRef = useRef<HTMLDivElement>(null);

  const isValid =
    street.trim().length > 0 &&
    city.trim().length > 0 &&
    state.length > 0 &&
    ZIP_REGEX.test(zip.trim());

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        streetWrapperRef.current &&
        !streetWrapperRef.current.contains(e.target as Node)
      ) {
        close();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [close]);

  async function selectSuggestion(placeId: string, fallbackFullText: string) {
    clear();
    setHighlightedIndex(-1);
    const details = await fetchPlaceDetails(placeId);
    if (details) {
      if (details.street) setStreet(details.street);
      else setStreet(fallbackFullText);
      if (details.city) setCity(details.city);
      if (details.state) setState(details.state);
      if (details.zip) setZip(details.zip);
    } else {
      // Place Details failed — leave the user with the picked text in Street.
      setStreet(fallbackFullText);
    }
  }

  function handleStreetChange(value: string) {
    setStreet(value);
    setHighlightedIndex(-1);
    if (!state) {
      clear();
      return;
    }
    onInputChange(value);
  }

  function handleStateChange(code: string) {
    setState(code);
    clear();
    setHighlightedIndex(-1);
  }

  function handleStreetKeyDown(e: React.KeyboardEvent) {
    if (!isOpen || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((i) => (i < suggestions.length - 1 ? i + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((i) => (i > 0 ? i - 1 : suggestions.length - 1));
    } else if (e.key === "Enter" && highlightedIndex >= 0) {
      e.preventDefault();
      const picked = suggestions[highlightedIndex];
      void selectSuggestion(picked.placeId, picked.fullText);
    } else if (e.key === "Escape") {
      close();
      setHighlightedIndex(-1);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid) return;
    clear();
    onSearch(`${street.trim()}, ${city.trim()}, ${state} ${zip.trim()}`);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 w-full max-w-xl"
    >
      {/* State (picked first so autocomplete can narrow by state) */}
      <div className="flex flex-col gap-1 sm:w-56">
        <label htmlFor="state" className="text-sm font-medium">
          State
        </label>
        <Select value={state} onValueChange={handleStateChange} disabled={loading}>
          <SelectTrigger id="state" className="w-full">
            <SelectValue placeholder="Select a state" />
          </SelectTrigger>
          <SelectContent>
            {US_STATES.map((s) => (
              <SelectItem key={s.code} value={s.code}>
                {s.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Street with autocomplete */}
      <div className="flex flex-col gap-1">
        <label htmlFor="street" className="text-sm font-medium">
          Street address
        </label>
        <div ref={streetWrapperRef} className="relative">
          <Input
            id="street"
            type="text"
            placeholder={state ? "123 Main St" : "Select a state first"}
            value={street}
            onChange={(e) => handleStreetChange(e.target.value)}
            onKeyDown={handleStreetKeyDown}
            disabled={loading || !state}
            autoComplete="off"
            role="combobox"
            aria-expanded={isOpen}
            aria-autocomplete="list"
            aria-controls="address-suggestions"
            aria-activedescendant={
              highlightedIndex >= 0 ? `suggestion-${highlightedIndex}` : undefined
            }
          />
          {isOpen && suggestions.length > 0 && (
            <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md">
              <ul id="address-suggestions" role="listbox">
                {suggestions.map((s, i) => (
                  <li
                    key={`${s.placeId}-${i}`}
                    id={`suggestion-${i}`}
                    role="option"
                    aria-selected={i === highlightedIndex}
                    className={`cursor-pointer px-3 py-2 text-sm ${
                      i === highlightedIndex
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-accent/50"
                    }`}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      void selectSuggestion(s.placeId, s.fullText);
                    }}
                    onMouseEnter={() => setHighlightedIndex(i)}
                  >
                    <span className="font-medium">{s.mainText}</span>{" "}
                    <span
                      className={`text-xs ${
                        i === highlightedIndex
                          ? "opacity-80"
                          : "text-muted-foreground"
                      }`}
                    >
                      {s.secondaryText}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="px-3 py-1.5 text-[10px] text-muted-foreground text-right border-t">
                Powered by Google
              </div>
            </div>
          )}
        </div>
      </div>

      {/* City | ZIP */}
      <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="city" className="text-sm font-medium">
            City
          </label>
          <Input
            id="city"
            type="text"
            placeholder="Austin"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            disabled={loading}
            autoComplete="off"
          />
        </div>
        <div className="flex flex-col gap-1 sm:w-32">
          <label htmlFor="zip" className="text-sm font-medium">
            ZIP code
          </label>
          <Input
            id="zip"
            type="text"
            inputMode="numeric"
            maxLength={10}
            placeholder="78701"
            value={zip}
            onChange={(e) => setZip(e.target.value)}
            disabled={loading}
            autoComplete="off"
          />
        </div>
      </div>

      <div>
        <Button type="submit" disabled={loading || !isValid}>
          {loading ? "Searching…" : "Search"}
        </Button>
      </div>
    </form>
  );
}
