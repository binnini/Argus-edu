import { useState, useEffect } from "react"
import {
  getGroups,
  createGroup,
  deleteGroup,
  addGroupMembers,
  removeGroupMember,
  type GroupResponse,
  type GroupMemberItem,
} from "@/api/teacher"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardHeader, CardTitle } from "@/components/ui/card"

export default function GroupManager() {
  const [groups, setGroups] = useState<GroupResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 새 그룹 생성
  const [newGroupName, setNewGroupName] = useState("")
  const [creating, setCreating] = useState(false)

  // 선택된 그룹
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null)

  // 새 멤버 추가
  const [newMemberStudentId, setNewMemberStudentId] = useState("")
  const [newMemberStudentName, setNewMemberStudentName] = useState("")
  const [addingMember, setAddingMember] = useState(false)

  async function fetchGroups() {
    setLoading(true)
    setError(null)
    try {
      const data = await getGroups()
      setGroups(data.groups)
    } catch (e) {
      setError(e instanceof Error ? e.message : "그룹 목록 조회 실패")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchGroups()
  }, [])

  async function handleCreateGroup() {
    if (!newGroupName.trim()) return
    setCreating(true)
    try {
      await createGroup(newGroupName.trim())
      setNewGroupName("")
      await fetchGroups()
    } catch (e) {
      setError(e instanceof Error ? e.message : "그룹 생성 실패")
    } finally {
      setCreating(false)
    }
  }

  async function handleDeleteGroup(groupId: number) {
    if (!confirm("그룹을 삭제하시겠습니까? 모든 멤버 정보도 함께 삭제됩니다.")) return
    try {
      await deleteGroup(groupId)
      if (selectedGroupId === groupId) setSelectedGroupId(null)
      await fetchGroups()
    } catch (e) {
      setError(e instanceof Error ? e.message : "그룹 삭제 실패")
    }
  }

  async function handleAddMember() {
    if (!selectedGroupId || !newMemberStudentId.trim() || !newMemberStudentName.trim()) return
    setAddingMember(true)
    try {
      const member: GroupMemberItem = {
        student_id: newMemberStudentId.trim(),
        student_name: newMemberStudentName.trim(),
      }
      await addGroupMembers(selectedGroupId, [member])
      setNewMemberStudentId("")
      setNewMemberStudentName("")
      await fetchGroups()
    } catch (e) {
      setError(e instanceof Error ? e.message : "멤버 추가 실패")
    } finally {
      setAddingMember(false)
    }
  }

  async function handleRemoveMember(groupId: number, studentId: string) {
    if (!confirm(`학생 ${studentId}을(를) 그룹에서 제거하시겠습니까?`)) return
    try {
      await removeGroupMember(groupId, studentId)
      await fetchGroups()
    } catch (e) {
      setError(e instanceof Error ? e.message : "멤버 제거 실패")
    }
  }

  const selectedGroup = groups.find((g) => g.id === selectedGroupId) ?? null

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Input
          placeholder="새 그룹 이름"
          value={newGroupName}
          onChange={(e) => setNewGroupName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreateGroup()}
          className="max-w-xs"
        />
        <Button onClick={handleCreateGroup} disabled={creating || !newGroupName.trim()}>
          {creating ? "생성 중..." : "그룹 생성"}
        </Button>
      </div>

      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">로딩 중...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 그룹 목록 */}
          <div className="space-y-2">
            <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">그룹 목록</h3>
            {groups.length === 0 && (
              <p className="text-sm text-muted-foreground">등록된 그룹이 없습니다.</p>
            )}
            {groups.map((group) => (
              <Card
                key={group.id}
                className={`cursor-pointer transition-colors ${selectedGroupId === group.id ? "border-primary" : ""}`}
                onClick={() => setSelectedGroupId(group.id)}
              >
                <CardHeader className="py-3 px-4 flex flex-row items-center justify-between space-y-0">
                  <CardTitle className="text-sm font-medium">
                    {group.name}
                    <span className="ml-2 text-xs text-muted-foreground">({group.members.length}명)</span>
                  </CardTitle>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); handleDeleteGroup(group.id) }}
                  >
                    삭제
                  </Button>
                </CardHeader>
              </Card>
            ))}
          </div>

          {/* 선택된 그룹 멤버 */}
          {selectedGroup && (
            <div className="space-y-3">
              <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">
                {selectedGroup.name} — 멤버
              </h3>

              {/* 멤버 추가 폼 */}
              <div className="flex gap-2 flex-wrap">
                <Input
                  placeholder="학생 ID"
                  value={newMemberStudentId}
                  onChange={(e) => setNewMemberStudentId(e.target.value)}
                  className="w-32"
                />
                <Input
                  placeholder="학생 이름"
                  value={newMemberStudentName}
                  onChange={(e) => setNewMemberStudentName(e.target.value)}
                  className="w-32"
                />
                <Button
                  size="sm"
                  onClick={handleAddMember}
                  disabled={addingMember || !newMemberStudentId.trim() || !newMemberStudentName.trim()}
                >
                  {addingMember ? "추가 중..." : "멤버 추가"}
                </Button>
              </div>

              {/* 멤버 목록 */}
              {selectedGroup.members.length === 0 ? (
                <p className="text-sm text-muted-foreground">멤버가 없습니다.</p>
              ) : (
                <div className="space-y-1">
                  {selectedGroup.members.map((member) => (
                    <div
                      key={member.student_id}
                      className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                    >
                      <span>
                        <span className="font-medium">{member.student_name}</span>
                        <span className="ml-2 text-muted-foreground text-xs">{member.student_id}</span>
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-500 hover:text-red-700 h-6 px-2"
                        onClick={() => handleRemoveMember(selectedGroup.id, member.student_id)}
                      >
                        제거
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
