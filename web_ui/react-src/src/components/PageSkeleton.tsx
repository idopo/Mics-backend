import Skeleton from './Skeleton'

export default function PageSkeleton() {
  return (
    <div className="page-skeleton" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <Skeleton style={{ height: '2rem', width: '40%' }} />
      <Skeleton style={{ height: '1rem', width: '70%' }} />
      <Skeleton style={{ height: '1rem', width: '60%' }} />
      <Skeleton style={{ height: '1rem', width: '80%' }} />
    </div>
  )
}
