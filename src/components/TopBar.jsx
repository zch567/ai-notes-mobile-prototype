export function TopBar({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between gap-4 px-5 pt-4">
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-blue-500">AI Notes</p>
        <h1 className="mt-1 text-[24px] font-semibold tracking-tight text-slate-950">{title}</h1>
        {subtitle ? <p className="mt-1 text-[13px] leading-5 text-slate-500">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}
