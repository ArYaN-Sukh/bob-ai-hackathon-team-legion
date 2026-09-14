interface Props {
  score: number | null
  tier: 'High' | 'Medium' | 'Low' | null
  major: number
  minor: number
  admin: number
}

const TIER_STYLES = {
  High: 'bg-red-50 border-red-200 text-red-700',
  Medium: 'bg-amber-50 border-amber-200 text-amber-700',
  Low: 'bg-green-50 border-green-200 text-green-700',
}

const TIER_BAR = {
  High: 'bg-red-500',
  Medium: 'bg-amber-500',
  Low: 'bg-green-500',
}

export default function RiskScoreCard({ score, tier, major, minor, admin }: Props) {
  if (!score || !tier) {
    return (
      <div className="rounded-lg border border-gray-200 p-4 bg-gray-50 text-center text-gray-500 text-sm">
        No risk score — run analysis first
      </div>
    )
  }

  const pct = Math.min((score / 500) * 100, 100)

  return (
    <div className={`rounded-lg border p-4 ${TIER_STYLES[tier]}`}>
      <div className="flex items-baseline justify-between mb-2">
        <div>
          <div className="text-3xl font-bold">{score.toFixed(0)}</div>
          <div className="text-xs uppercase tracking-wide font-semibold">{tier} Risk</div>
        </div>
        <div className="text-right text-xs space-y-1">
          <div><span className="font-semibold text-red-600">{major}</span> Major</div>
          <div><span className="font-semibold text-amber-600">{minor}</span> Minor</div>
          <div><span className="font-semibold text-blue-600">{admin}</span> Admin</div>
        </div>
      </div>
      <div className="w-full bg-white/60 rounded-full h-2 mt-2">
        <div
          className={`h-2 rounded-full transition-all ${TIER_BAR[tier]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
