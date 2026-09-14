export default function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center py-16 text-gray-400 text-sm">
      {message}
    </div>
  )
}
