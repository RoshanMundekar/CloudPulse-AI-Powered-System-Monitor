/**
 * Skeleton — shimmer placeholder for loading states.
 * Usage: <Skeleton className="h-8 w-32" />  or  <Skeleton.Card />
 */
export default function Skeleton({ className = '', style }) {
  return <div className={`skeleton ${className}`} style={style} />
}

Skeleton.Card = function SkeletonCard({ rows = 3 }) {
  return (
    <div className="glass-card p-5 space-y-3 animate-fade-in">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-16" />
      {Array.from({ length: rows - 2 }).map((_, i) => (
        <Skeleton key={i} className="h-3 w-full" />
      ))}
    </div>
  )
}

Skeleton.Chart = function SkeletonChart({ height = 200 }) {
  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-5 w-14" />
      </div>
      <Skeleton className={`w-full rounded-lg`} style={{ height }} />
    </div>
  )
}

Skeleton.Row = function SkeletonRow() {
  return (
    <div className="glass-card p-4 flex items-center gap-4">
      <Skeleton className="h-8 w-8 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-3 w-48" />
      </div>
      <Skeleton className="h-6 w-16 rounded-full" />
    </div>
  )
}
