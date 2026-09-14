import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { User, AlertTriangle } from 'lucide-react'
import { getPatients } from '../api/client'

export default function Patients() {
  const { data: patients, isLoading, error } = useQuery({
    queryKey: ['patients'],
    queryFn: () => getPatients(),
  })

  if (isLoading) return <div className="p-8 text-center text-text-tertiary">Loading patients...</div>
  if (error) return <div className="p-8 text-center text-severity-major">Failed to load patients.</div>

  return (
    <div className="space-y-section">
      <div>
        <h1 className="text-2xl font-semibold text-text-primary">Patients</h1>
        <p className="text-sm text-text-secondary mt-1">
          Review enrolled patients and their protocol deviation history.
        </p>
      </div>

      <div className="bg-surface rounded-lg border border-border shadow-card overflow-hidden">
        <div className="px-card py-3 border-b border-border-light">
          <h2 className="font-semibold text-text-primary">All Patients</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-alt text-left text-xs text-text-secondary uppercase tracking-wide">
                <th className="px-4 py-3">Patient ID</th>
                <th className="px-4 py-3">Site</th>
                <th className="px-4 py-3">Age</th>
                <th className="px-4 py-3">Sex</th>
                <th className="px-4 py-3">Enrollment Date</th>
                <th className="px-4 py-3">Open Deviations</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-light">
              {patients && patients.length > 0 ? patients.map(patient => (
                <tr key={patient.id} className="hover:bg-surface-alt transition-colors">
                  <td className="px-4 py-3">
                    <Link
                      to={`/patients/${patient.id}`}
                      className="font-mono font-medium text-clinical-navy hover:underline"
                    >
                      {patient.id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-text-secondary">{patient.site_id}</td>
                  <td className="px-4 py-3 text-text-secondary">{patient.age}</td>
                  <td className="px-4 py-3 text-text-secondary">{patient.sex}</td>
                  <td className="px-4 py-3 text-text-secondary">
                    {new Date(patient.enrollment_date).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    {patient.open_deviation_count > 0 ? (
                      <span className="flex items-center gap-1 text-severity-major font-medium">
                        <AlertTriangle className="w-4 h-4" />
                        {patient.open_deviation_count}
                      </span>
                    ) : (
                      <span className="text-text-tertiary">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/patients/${patient.id}`}
                      className="text-sm text-clinical-navy hover:underline font-medium"
                    >
                      View Timeline
                    </Link>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-text-tertiary">
                    No patients found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
