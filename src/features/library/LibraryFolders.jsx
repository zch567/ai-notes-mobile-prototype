import { useState } from "react";

export const ALL_FOLDERS_ID = "all";
export const UNCATEGORIZED_FOLDER_ID = "uncategorized";

export function LibraryFolderBar({
  folders = [],
  records = [],
  activeFolderId = ALL_FOLDERS_ID,
  onSelectFolder = () => {},
  onCreateFolder = () => {},
  onRenameFolder = () => {},
  onDeleteFolder = () => {},
}) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [renameName, setRenameName] = useState("");
  const folderCounts = getFolderCounts(records);
  const activeFolder = folders.find((folder) => folder.id === activeFolderId);
  const isCustomFolder = Boolean(activeFolder);

  function submitNewFolder() {
    const name = newName.trim();
    if (!name) return;
    onCreateFolder(name);
    setNewName("");
    setCreating(false);
  }

  function startRename() {
    if (!activeFolder) return;
    setRenameName(activeFolder.name);
    setRenaming(true);
  }

  function submitRename() {
    const name = renameName.trim();
    if (!activeFolder || !name) return;
    onRenameFolder(activeFolder.id, name);
    setRenaming(false);
    setRenameName("");
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3 px-5">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">Folders</p>
          <p className="mt-1 text-[12px] text-slate-500">笔记库和导图库共用同一套文件夹</p>
        </div>
        <button
          type="button"
          onClick={() => setCreating((current) => !current)}
          className="shrink-0 rounded-2xl bg-blue-600 px-3 py-2 text-[12px] font-semibold text-white shadow-sm"
        >
          新建
        </button>
      </div>

      {creating ? (
        <div className="mx-5 flex items-center gap-2 rounded-2xl border border-blue-100 bg-white px-3 py-2 shadow-sm">
          <input
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") submitNewFolder();
              if (event.key === "Escape") setCreating(false);
            }}
            autoFocus
            maxLength={18}
            placeholder="例如：期末复习"
            className="min-w-0 flex-1 bg-transparent text-[13px] font-semibold text-slate-700 outline-none placeholder:text-slate-300"
          />
          <button type="button" onClick={submitNewFolder} className="rounded-xl bg-blue-600 px-3 py-1.5 text-[12px] font-semibold text-white">
            创建
          </button>
          <button type="button" onClick={() => setCreating(false)} className="rounded-xl px-2 py-1.5 text-[12px] font-semibold text-slate-400">
            取消
          </button>
        </div>
      ) : null}

      <div className="flex gap-2 overflow-x-auto px-5 pb-1">
        <FolderChip
          active={activeFolderId === ALL_FOLDERS_ID}
          label="全部"
          count={records.length}
          onClick={() => onSelectFolder(ALL_FOLDERS_ID)}
        />
        <FolderChip
          active={activeFolderId === UNCATEGORIZED_FOLDER_ID}
          label="未分类"
          count={folderCounts.uncategorized}
          onClick={() => onSelectFolder(UNCATEGORIZED_FOLDER_ID)}
        />
        {folders.map((folder) => (
          <FolderChip
            key={folder.id}
            active={activeFolderId === folder.id}
            label={folder.name}
            count={folderCounts.byId.get(folder.id) || 0}
            onClick={() => onSelectFolder(folder.id)}
          />
        ))}
      </div>

      {isCustomFolder ? (
        <div className="mx-5 flex items-center justify-between gap-3 rounded-2xl border border-blue-100 bg-blue-50 px-3 py-2">
          {renaming ? (
            <>
              <input
                value={renameName}
                onChange={(event) => setRenameName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") submitRename();
                  if (event.key === "Escape") setRenaming(false);
                }}
                autoFocus
                maxLength={18}
                className="min-w-0 flex-1 rounded-xl bg-white px-3 py-1.5 text-[12px] font-semibold text-slate-700 outline-none"
              />
              <button type="button" onClick={submitRename} className="shrink-0 text-[12px] font-semibold text-blue-700">
                保存
              </button>
              <button type="button" onClick={() => setRenaming(false)} className="shrink-0 text-[12px] font-semibold text-slate-500">
                取消
              </button>
            </>
          ) : (
            <>
              <p className="min-w-0 truncate text-[12px] font-semibold text-blue-800">当前文件夹：{activeFolder.name}</p>
              <div className="flex shrink-0 gap-2">
                <button type="button" onClick={startRename} className="text-[12px] font-semibold text-blue-700">
                  重命名
                </button>
                <button type="button" onClick={() => onDeleteFolder(activeFolder.id)} className="text-[12px] font-semibold text-slate-500">
                  删除
                </button>
              </div>
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}

export function FolderSelect({ folders = [], value = "", onChange = () => {} }) {
  return (
    <label className="flex min-w-0 items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-[12px] font-semibold text-slate-500">
      <span className="shrink-0">移动到</span>
      <select
        value={value || ""}
        onChange={(event) => onChange(event.target.value)}
        className="min-w-0 flex-1 bg-transparent text-[12px] font-semibold text-slate-700 outline-none"
      >
        <option value="">未分类</option>
        {folders.map((folder) => (
          <option key={folder.id} value={folder.id}>
            {folder.name}
          </option>
        ))}
      </select>
    </label>
  );
}

export function filterRecordsByFolder(records, activeFolderId) {
  if (activeFolderId === UNCATEGORIZED_FOLDER_ID) {
    return records.filter((record) => !record.folderId);
  }

  if (activeFolderId && activeFolderId !== ALL_FOLDERS_ID) {
    return records.filter((record) => record.folderId === activeFolderId);
  }

  return records;
}

export function getFolderName(folders, folderId) {
  if (!folderId) return "未分类";
  return folders.find((folder) => folder.id === folderId)?.name || "未分类";
}

function FolderChip({ active, label, count, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`shrink-0 rounded-2xl border px-3 py-2 text-[12px] font-semibold transition ${
        active
          ? "border-blue-500 bg-blue-600 text-white shadow-sm"
          : "border-slate-200 bg-white text-slate-600"
      }`}
    >
      {label}
      <span className={`ml-2 rounded-full px-1.5 py-0.5 text-[10px] ${active ? "bg-white/20 text-white" : "bg-slate-100 text-slate-400"}`}>
        {count}
      </span>
    </button>
  );
}

function getFolderCounts(records) {
  const byId = new Map();
  let uncategorized = 0;

  records.forEach((record) => {
    if (!record.folderId) {
      uncategorized += 1;
      return;
    }

    byId.set(record.folderId, (byId.get(record.folderId) || 0) + 1);
  });

  return { byId, uncategorized };
}
