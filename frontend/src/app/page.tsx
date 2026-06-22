import { ScenarioStudio } from "@/components/studio/ScenarioStudio"

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 p-4 font-sans text-slate-200">
      <div className="max-w-[1920px] mx-auto">
        <ScenarioStudio />
      </div>
    </main>
  )
}
