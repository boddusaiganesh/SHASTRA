import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface CrimesState {
  mapCrimes: unknown[];
  selectedCrime: unknown | null;
  filters: {
    dateFrom: string;
    dateTo: string;
    crimeType: string;
    district: string;
    timeOfDay: string;
    viewMode: "heatmap" | "cluster" | "pins";
  };
  loading: boolean;
}

const initialState: CrimesState = {
  mapCrimes: [],
  selectedCrime: null,
  filters: {
    dateFrom: "",
    dateTo: "",
    crimeType: "All",
    district: "All Districts",
    timeOfDay: "All",
    viewMode: "pins",
  },
  loading: false,
};

const crimesSlice = createSlice({
  name: "crimes",
  initialState,
  reducers: {
    setMapCrimes: (state, action: PayloadAction<unknown[]>) => { 
      state.mapCrimes = Array.isArray(action.payload) ? action.payload : ((action.payload as any)?.crimes || []); 
    },
    setSelectedCrime: (state, action: PayloadAction<unknown | null>) => { state.selectedCrime = action.payload; },
    setFilters: (state, action: PayloadAction<Partial<CrimesState["filters"]>>) => { state.filters = { ...state.filters, ...action.payload }; },
    setLoading: (state, action: PayloadAction<boolean>) => { state.loading = action.payload; },
  },
});

export const { setMapCrimes, setSelectedCrime, setFilters, setLoading } = crimesSlice.actions;
export default crimesSlice.reducer;
