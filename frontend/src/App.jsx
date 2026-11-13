import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext.jsx";
import DashboardLayout from "./layout/DashboardLayout.jsx";
import ChatPage from "./pages/chat/ChatPage.jsx";
import UploadHistoryPage from "./pages/upload-history/UploadHistoryPage.jsx";
import ViewHistoryPage from "./pages/view-history/ViewHistoryPage.jsx";
import "./App.css";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<DashboardLayout />}>
            <Route index element={<ChatPage />} />
            <Route path="upload-history" element={<UploadHistoryPage />} />
            <Route path="history" element={<ViewHistoryPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
