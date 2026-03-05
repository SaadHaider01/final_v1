import { useState } from 'react';
import axios from 'axios';
import { API_BASE_URL, API_ENDPOINTS } from '../config/apiConfig';

export function useApiClient() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // --------------------------------------------------
  // Existing methods (unchanged)
  // --------------------------------------------------
  const ingestSyllabus = async (formData) => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post(
        `${API_BASE_URL}${API_ENDPOINTS.INGEST_SYLLABUS}`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      return response.data;
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to ingest syllabus';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const analyzeQuestion = async (payload) => {
    setLoading(true);
    setError(null);
    try {
      const isFormData = payload instanceof FormData;
      const response = await axios.post(
        `${API_BASE_URL}${API_ENDPOINTS.ANALYZE_QUESTION}`,
        payload,
        isFormData ? { headers: { 'Content-Type': 'multipart/form-data' } } : undefined
      );
      return response.data;
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to analyze question';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const listSyllabi = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_BASE_URL}${API_ENDPOINTS.LIST_SYLLABI}`);
      return response.data;
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to fetch syllabi';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const deleteSyllabus = async (syllabusId) => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post(
        `${API_BASE_URL}${API_ENDPOINTS.DELETE_SYLLABUS}`,
        { syllabus_id: syllabusId }
      );
      return response.data;
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to delete syllabus';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------
  // Upgrade B — URL-based ingestion
  // --------------------------------------------------
  const ingestFromUrl = async (payload) => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post(
        `${API_BASE_URL}${API_ENDPOINTS.INGEST_FROM_URL}`,
        payload,
        { headers: { 'Content-Type': 'application/json' } }
      );
      return response.data;
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to fetch syllabus from URL';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------
  // Feature 4 — BOS endpoints
  // --------------------------------------------------
  const getBos = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}${API_ENDPOINTS.BOS}`);
      return response.data;
    } catch {
      return [];
    }
  };

  const getDepartments = async (bos = '') => {
    try {
      const params = bos ? { bos } : {};
      const response = await axios.get(`${API_BASE_URL}${API_ENDPOINTS.DEPARTMENTS}`, { params });
      return response.data;
    } catch {
      return [];
    }
  };

  const getSubjects = async (semester = '') => {
    try {
      const params = semester ? { semester } : {};
      const response = await axios.get(`${API_BASE_URL}${API_ENDPOINTS.SUBJECTS}`, { params });
      return response.data;
    } catch {
      return [];
    }
  };

  return {
    loading,
    error,
    ingestSyllabus,
    analyzeQuestion,
    listSyllabi,
    deleteSyllabus,
    ingestFromUrl,
    getBos,
    getDepartments,
    getSubjects,
  };
}
