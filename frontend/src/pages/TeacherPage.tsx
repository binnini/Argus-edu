import { useState, useEffect } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import PasswordGate from "@/components/teacher/PasswordGate"
import DashboardHeader from "@/components/teacher/DashboardHeader"
import ProblemManager from "@/components/teacher/ProblemManager"
import SubmissionOverview from "@/components/teacher/SubmissionOverview"
import ReviewQueue from "@/components/teacher/ReviewQueue"

export default function TeacherPage() {
  const [authenticated, setAuthenticated] = useState(false)

  useEffect(() => {
    const pw = localStorage.getItem("argus_teacher_pw")
    if (pw) setAuthenticated(true)
  }, [])

  function handleLogout() {
    localStorage.removeItem("argus_teacher_pw")
    setAuthenticated(false)
  }

  if (!authenticated) {
    return <PasswordGate onSuccess={() => setAuthenticated(true)} />
  }

  return (
    <div className="min-h-screen bg-background">
      <DashboardHeader onLogout={handleLogout} />
      <main className="max-w-7xl mx-auto px-4 py-8">
        <Tabs defaultValue="queue">
          <TabsList className="mb-6">
            <TabsTrigger value="problems">문제 관리</TabsTrigger>
            <TabsTrigger value="submissions">풀이 현황</TabsTrigger>
            <TabsTrigger value="queue">검토 큐</TabsTrigger>
          </TabsList>
          <TabsContent value="problems">
            <ProblemManager />
          </TabsContent>
          <TabsContent value="submissions">
            <SubmissionOverview />
          </TabsContent>
          <TabsContent value="queue">
            <ReviewQueue />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
