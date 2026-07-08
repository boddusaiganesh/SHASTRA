import api from './api';
import { ENDPOINTS } from '../constants/apiEndpoints';

export const evidenceService = {
  getEvidenceList: async (crimeId: string) => {
    const res = await api.get(ENDPOINTS.EVIDENCE.BY_CRIME(crimeId));
    return res.data || [];
  },
  
  uploadEvidence: async (crimeId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const res = await api.post(ENDPOINTS.EVIDENCE.BY_CRIME(crimeId), formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },
  
  downloadEvidence: async (evidenceId: string) => {
    const res = await api.get(ENDPOINTS.EVIDENCE.DOWNLOAD(evidenceId), { responseType: 'blob' });
    return res.data;
  }
};
