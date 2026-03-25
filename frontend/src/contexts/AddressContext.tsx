import { createContext, useContext, useState, useCallback } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

interface AddressContextValue {
  address: string | null;
  setAddress: (address: string) => void;
  clearAddress: () => void;
}

const AddressContext = createContext<AddressContextValue | null>(null);

export function AddressProvider({ children }: { children: ReactNode }) {
  const [address, setAddressState] = useState<string | null>(null);
  const navigate = useNavigate();

  const setAddress = useCallback(
    (addr: string) => {
      setAddressState(addr);
      navigate("/reps");
    },
    [navigate]
  );

  const clearAddress = useCallback(() => {
    setAddressState(null);
    navigate("/");
  }, [navigate]);

  return (
    <AddressContext.Provider value={{ address, setAddress, clearAddress }}>
      {children}
    </AddressContext.Provider>
  );
}

export function useAddress() {
  const ctx = useContext(AddressContext);
  if (!ctx) throw new Error("useAddress must be used within AddressProvider");
  return ctx;
}
