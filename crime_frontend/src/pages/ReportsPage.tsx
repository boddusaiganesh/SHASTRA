import React, { useEffect, useState } from "react";
import { FileText, Download, Plus, CheckCircle, Clock, Loader2, Eye, X, Trash2 } from "lucide-react";
import { reportService } from "../services/reportService";
import { useDistricts } from "../hooks/useDistricts";
import LoadingSpinner from "../components/common/LoadingSpinner";

const REPORT_TYPES = [
  { value: "DISTRICT_SUMMARY", label: "District Crime Summary" },
  { value: "CRIME_TREND", label: "State-Wide Overview" },
  { value: "HOTSPOT", label: "Hotspot Analysis Report" },
  { value: "OFFENDER", label: "Offender Profile Report" },
  { value: "PREDICTION_REPORT", label: "Predictive Intelligence Report" },
];

interface SavedReport {
  report_id: string; report_type: string; district?: string;
  generated_at: string; status: string; file_size?: string;
}

const ReportsPage: React.FC = () => {
  const [savedReports, setSavedReports] = useState<SavedReport[]>([]);
  const [reportType, setReportType] = useState(REPORT_TYPES[0].value);
  const [district, setDistrict] = useState("All Districts");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const districts = useDistricts();
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [successMsg, setSuccessMsg] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);
  const [viewingPdf, setViewingPdf] = useState<string | null>(null);

  const handleViewPdf = async (reportId: string) => {
    try {
      const blob = await reportService.download(reportId, "pdf");
      if (blob) {
        const url = URL.createObjectURL(blob);
        setViewingPdf(url);
      } else {
        setSuccessMsg(`Failed to load report ${reportId}.`);
        setTimeout(() => setSuccessMsg(""), 4000);
      }
    } catch (error) {
      setSuccessMsg("Failed to load PDF viewer.");
      setTimeout(() => setSuccessMsg(""), 3000);
    }
  };

  const handleDelete = async (reportId: string) => {
    if (!confirm("Are you sure you want to delete this report?")) return;
    try {
      await reportService.deleteReport(reportId);
      setSavedReports(prev => prev.filter(r => r.report_id !== reportId));
      setTotalCount(prev => Math.max(0, prev - 1));
      setSuccessMsg("Report deleted successfully");
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (error) {
      setSuccessMsg("Failed to delete report.");
      setTimeout(() => setSuccessMsg(""), 3000);
    }
  };

  useEffect(() => {
    reportService.getSavedList(page, pageSize).then((d: any) => {
      setSavedReports(Array.isArray(d) ? d : (d?.reports || d?.data || []));
      setTotalCount(d?.total_count || 0);
      setLoading(false);
    });
  }, [page, pageSize]);

  const handleGenerate = async () => {
    setGenerating(true);
    setSuccessMsg("");
    try {
      const params: Record<string, string> = { report_type: reportType };
      if (district !== "All Districts") params.district_id = district;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const result = await reportService.generateReport(params);
      if (result) {
        setSavedReports((prev) => [result as unknown as SavedReport, ...prev]);
        setSuccessMsg("Report generated successfully!");
        setTimeout(() => setSuccessMsg(""), 3000);
      }
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async (reportId: string, format: string = "pdf") => {
    try {
      const blob = await reportService.download(reportId, format);
      if (blob) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Report_${reportId}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } else {
        setSuccessMsg(`Failed to download report ${reportId} as ${format.toUpperCase()}.`);
        setTimeout(() => setSuccessMsg(""), 4000);
      }
    } catch (error) {
      setSuccessMsg("Download failed. Please try again.");
      setTimeout(() => setSuccessMsg(""), 3000);
    }
  };

  if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Loading reports..." /></div>;

  return (
    <div className="flex-1 min-h-0 w-full overflow-y-auto overflow-x-hidden custom-scrollbar p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Executive Reports</h1>
          <p className="text-sm text-slate-400">Generate and download official crime intelligence reports</p>
        </div>
      </div>

      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Generate New Report</h3>
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1">
            <label className="block text-xs text-slate-400 mb-1">Report Type</label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              className="w-full bg-slate-900 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-blue-500"
            >
              {REPORT_TYPES.map((rt) => (
                <option key={rt.value} value={rt.value}>{rt.label}</option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-xs text-slate-400 mb-1">District Focus</label>
            <select
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
              className="w-full bg-slate-900 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-blue-500"
            >
              <option value="All Districts">All Districts (State Wide)</option>
              {districts.map((d) => (
                <option key={d.district_id} value={d.district_id}>{d.district_name}</option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-xs text-slate-400 mb-1">From Date</label>
            <input 
              type="date" 
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full bg-slate-900 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-blue-500 [color-scheme:dark]"
            />
          </div>
          <div className="flex-1">
            <label className="block text-xs text-slate-400 mb-1">To Date</label>
            <input 
              type="date" 
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full bg-slate-900 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-blue-500 [color-scheme:dark]"
            />
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {generating ? <Loader2 className="h-5 w-5 animate-spin" /> : <Plus className="h-5 w-5" />}
            Generate Report
          </button>
        </div>
        {successMsg && (
          <div className="mt-3 flex items-center gap-2 text-green-400 text-sm">
            <CheckCircle className="h-4 w-4" />
            {successMsg}
          </div>
        )}
      </div>

      <div>
        <h3 className="text-sm font-semibold text-white mb-4">Saved Reports</h3>
        <div className="space-y-3">
          {(Array.isArray(savedReports) ? savedReports : []).map((report) => (
            <div key={report.report_id} className="flex items-center justify-between p-4 bg-slate-800/50 border border-slate-700/50 rounded-xl">
              <div className="flex items-center gap-4">
                <div className="h-10 w-10 rounded-full bg-blue-900/30 flex items-center justify-center text-blue-400">
                  <FileText className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">{report.report_type}</p>
                  <div className="flex items-center gap-3 text-xs text-slate-400 mt-1">
                    <span>ID: {report.report_id}</span>
                    <span>•</span>
                    <span>{report.district || "State Wide"}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{new Date(report.generated_at || (report as any).created_at || new Date()).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-1 rounded-full ${report.status === "READY" || report.status === "Ready" || report.status === "Completed" ? "bg-green-900/30 text-green-400" : "bg-yellow-900/30 text-yellow-400"}`}>
                  {report.status || "Ready"}
                </span>
                <button
                  onClick={() => handleViewPdf(report.report_id)}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs text-emerald-400 hover:text-emerald-300 hover:bg-emerald-900/20 rounded-lg transition-colors"
                >
                  <Eye className="h-4 w-4" /> View
                </button>
                <button
                  onClick={() => handleDownload(report.report_id, 'pdf')}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs text-blue-400 hover:text-blue-300 hover:bg-blue-900/20 rounded-lg transition-colors"
                >
                  <Download className="h-4 w-4" /> PDF
                </button>
                <button
                  onClick={() => handleDownload(report.report_id, 'csv')}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs text-blue-400 hover:text-blue-300 hover:bg-blue-900/20 rounded-lg transition-colors"
                >
                  <Download className="h-4 w-4" /> CSV
                </button>
                <button
                  onClick={() => handleDelete(report.report_id)}
                  className="flex items-center justify-center p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-900/20 rounded-lg transition-colors ml-2"
                  title="Delete Report"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
          {savedReports.length === 0 && (
            <div className="text-center py-8 text-slate-500 text-sm">No saved reports found.</div>
          )}
          {/* Pagination Controls */}
          <div className="flex items-center justify-between p-4 border-t border-slate-700/50 mt-4">
            <span className="text-sm text-slate-400">Total: {totalCount}</span>
            <div className="flex gap-2 items-center">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 bg-slate-800 text-slate-300 rounded disabled:opacity-50"
              >
                Prev
              </button>
              <span className="text-sm text-white px-2">Page {page} {totalCount > 0 && `of ${Math.max(1, Math.ceil(totalCount / pageSize))}`}</span>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={page >= Math.max(1, Math.ceil(totalCount / pageSize))}
                className="px-3 py-1 bg-slate-800 text-slate-300 rounded disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </div>

      {viewingPdf && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl w-full max-w-5xl h-[90vh] flex flex-col">
            <div className="flex justify-between items-center p-4 border-b border-slate-700">
              <h2 className="text-lg font-bold text-white">Report Viewer</h2>
              <button 
                onClick={() => {
                  URL.revokeObjectURL(viewingPdf);
                  setViewingPdf(null);
                }} 
                className="text-slate-400 hover:text-white"
              >
                <X className="h-6 w-6" />
              </button>
            </div>
            <div className="flex-1 p-2 bg-slate-800">
              <iframe src={viewingPdf} className="w-full h-full rounded border border-slate-700 bg-white" title="PDF Viewer" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReportsPage;
