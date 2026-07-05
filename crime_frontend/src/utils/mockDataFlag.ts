export function flagMockDataUsed() {
  (window as any).__using_mock_data = true;
  window.dispatchEvent(new CustomEvent("mock-data-detected"));
}
