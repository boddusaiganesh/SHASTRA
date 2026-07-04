import api from './api';

export const evidenceService = {
  getEvidenceList: async (crimeId: string) => {
    const res = await api.get(`/evidence/${crimeId}`);
    return res.data.data;
  },
  
  uploadEvidence: async (crimeId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const res = await api.post(`/evidence/${crimeId}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  }
};
