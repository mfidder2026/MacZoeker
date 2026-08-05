import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

export const getLatest = () => api.get("/latest").then((r) => r.data);
export const getRuns = () => api.get("/scan/runs").then((r) => r.data);
export const runScan = () => api.post("/scan/run").then((r) => r.data);
export const cancelScan = () => api.post("/scan/cancel").then((r) => r.data);
export const getCurrentRun = () => api.get("/scan/current").then((r) => r.data);
export const getSettings = () => api.get("/settings").then((r) => r.data);
export const updateSettings = (payload) => api.put("/settings", payload).then((r) => r.data);
export const getLatestReport = () => api.get("/reports/latest").then((r) => r.data);
export const getReport = (id) => api.get(`/reports/${id}`).then((r) => r.data);
export const sendTestEmail = () => api.post("/email/test").then((r) => r.data);
