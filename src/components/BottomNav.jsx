import { NAV_ITEMS } from "../app/navigation";

export function BottomNav({ active, onChange, isWebView = false, compact = false }) {
  return (
    <div
      className={`border-t border-slate-200 bg-white/95 px-2 backdrop-blur ${compact ? "pt-2" : "pt-3"}`}
      style={{ paddingBottom: isWebView ? "max(10px, env(safe-area-inset-bottom))" : "12px" }}
    >
      <div className="grid grid-cols-5 items-end gap-1">
        {NAV_ITEMS.map((tab) => {
          const isActive = active === tab.id;
          const isPrimary = tab.id === "ai";
          return (
            <button
              key={tab.id}
              onClick={() => onChange(tab.id)}
              className={`flex flex-col items-center justify-center rounded-2xl px-2 font-medium ${
                isActive ? "bg-blue-50 text-blue-700" : "text-slate-400"
              } ${compact ? "py-1.5 text-[10px]" : "py-2 text-[11px]"} ${isPrimary ? (compact ? "-mt-5" : "-mt-7") : ""}`}
            >
              <span
                className={`grid leading-none ${
                  isPrimary
                    ? `${compact ? "mb-0.5 h-12 w-12 rounded-[20px] text-[20px]" : "mb-1 h-14 w-14 rounded-[24px] text-[22px]"} place-items-center bg-blue-600 text-white shadow-lg shadow-blue-100`
                    : compact ? "text-[16px]" : "text-[18px]"
                }`}
              >
                {tab.icon}
              </span>
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
