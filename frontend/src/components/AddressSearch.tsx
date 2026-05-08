import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAddressAutocomplete } from "@/hooks/useAddressAutocomplete";

interface AddressSearchProps {
  onSearch: (address: string) => void;
  loading: boolean;
}

export function AddressSearch({ onSearch, loading }: AddressSearchProps) {
  const [address, setAddress] = useState("");
  const [selectedFullText, setSelectedFullText] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const { suggestions, isOpen, onInputChange, close, clear } =
    useAddressAutocomplete();
  const wrapperRef = useRef<HTMLDivElement>(null);

  const hasValidSelection =
    address.trim().length > 0 && address === selectedFullText;

  // Click-outside to dismiss dropdown
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        close();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [close]);

  // Selecting a suggestion populates the input and auto-submits the search
  function selectSuggestion(fullText: string) {
    setAddress(fullText);
    setSelectedFullText(fullText);
    clear();
    setHighlightedIndex(-1);
    onSearch(fullText);
  }

  function handleInputChange(value: string) {
    setAddress(value);
    // Any edit invalidates the prior pick — user must re-select from dropdown
    if (value !== selectedFullText) setSelectedFullText("");
    setHighlightedIndex(-1);
    onInputChange(value);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!isOpen || suggestions.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((i) =>
        i < suggestions.length - 1 ? i + 1 : 0
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((i) =>
        i > 0 ? i - 1 : suggestions.length - 1
      );
    } else if (e.key === "Enter" && highlightedIndex >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[highlightedIndex].fullText);
    } else if (e.key === "Escape") {
      close();
      setHighlightedIndex(-1);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (hasValidSelection) {
      clear();
      onSearch(address.trim());
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 w-full max-w-xl">
      <div className="flex gap-3">
        <div ref={wrapperRef} className="relative flex-1">
          <Input
            type="text"
            placeholder="Start typing your address…"
            value={address}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full"
            disabled={loading}
            autoComplete="off"
            role="combobox"
            aria-expanded={isOpen}
            aria-autocomplete="list"
            aria-controls="address-suggestions"
            aria-activedescendant={
              highlightedIndex >= 0
                ? `suggestion-${highlightedIndex}`
                : undefined
            }
          />
          {isOpen && suggestions.length > 0 && (
            <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md">
              <ul
                id="address-suggestions"
                role="listbox"
              >
                {suggestions.map((s, i) => (
                  <li
                    key={`${s.fullText}-${i}`}
                    id={`suggestion-${i}`}
                    role="option"
                    aria-selected={i === highlightedIndex}
                    className={`cursor-pointer px-3 py-2 text-sm ${
                      i === highlightedIndex
                        ? "bg-blue-600 text-white"
                        : "hover:bg-accent/50"
                    }`}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      selectSuggestion(s.fullText);
                    }}
                    onMouseEnter={() => setHighlightedIndex(i)}
                  >
                    <span className="font-medium">{s.mainText}</span>{" "}
                    <span
                      className={`text-xs ${
                        i === highlightedIndex
                          ? "text-blue-100"
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
        <Button type="submit" disabled={loading || !hasValidSelection}>
          {loading ? "Searching…" : "Search"}
        </Button>
      </div>
    </form>
  );
}
