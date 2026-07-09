import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/hooks/useTheme'
import { AppLayout } from '@/components/AppLayout'
import { UploadLibraryPage } from '@/pages/UploadLibraryPage'
import { ResearchChatPage } from '@/pages/ResearchChatPage'
import { LiteratureReviewPage } from '@/pages/LiteratureReviewPage'
import { PaperComparisonPage } from '@/pages/PaperComparisonPage'
import { GapAnalysisPage } from '@/pages/GapAnalysisPage'
import { CitationExplorerPage } from '@/pages/CitationExplorerPage'
import { HealthDashboardPage } from '@/pages/HealthDashboardPage'
import { ExportCenterPage } from '@/pages/ExportCenterPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { Skeleton } from '@/components/ui'

// The force-directed graph renderer pulls in a large canvas/physics library —
// code-split it so the main bundle (and every other page) stays lean.
const KnowledgeGraphPage = lazy(() => import('@/pages/KnowledgeGraphPage').then((m) => ({ default: m.KnowledgeGraphPage })))

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 5_000 } },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<UploadLibraryPage />} />
              <Route path="/chat" element={<ResearchChatPage />} />
              <Route path="/literature-review" element={<LiteratureReviewPage />} />
              <Route path="/compare" element={<PaperComparisonPage />} />
              <Route path="/gaps" element={<GapAnalysisPage />} />
              <Route path="/citations" element={<CitationExplorerPage />} />
              <Route
                path="/graph"
                element={
                  <Suspense fallback={<Skeleton className="h-[600px] w-full" />}>
                    <KnowledgeGraphPage />
                  </Suspense>
                }
              />
              <Route path="/health" element={<HealthDashboardPage />} />
              <Route path="/export" element={<ExportCenterPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

