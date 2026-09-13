import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  Loader2,
  Search,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { AppHeader } from "@/components/AppHeader";
import { AuthGuard } from "@/components/auth-guard";
import { fetchDocuments, uploadDocument, deleteDocument } from "@/lib/api-client";
import type { DocumentResponse } from "@/lib/api-types";

export const Route = createFileRoute("/documents")({
  head: () => ({
    meta: [
      { title: "Safety Management | SafeVision AI" },
      {
        name: "description",
        content:
          "Manage approved safety documents and the knowledge base used by the AI system for recommendations.",
      },
      { property: "og:title", content: "Safety Management | SafeVision AI" },
      {
        property: "og:description",
        content: "Approved safety policies and SOPs powering AI safety recommendations.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: SafetyManagementPage,
});

// Document type display config (matches backend DocumentType enum)
const DOC_TYPE_LABELS: Record<string, string> = {
  txt: "TXT",
  markdown: "MD",
  pdf: "PDF",
};
const DOC_TYPE_TONE: Record<string, string> = {
  pdf: "border-destructive/30 bg-destructive/10 text-destructive",
  txt: "border-primary/30 bg-primary/10 text-primary",
  markdown: "border-blue-500/30 bg-blue-500/10 text-blue-600",
};

// Document status display config (matches backend DocumentStatus enum)
const DOC_STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
  deleted: "Deleted",
};
const DOC_STATUS_TONE: Record<string, string> = {
  ready: "bg-green-500/10 text-green-600",
  pending: "bg-amber-500/10 text-amber-600",
  processing: "bg-blue-500/10 text-blue-600",
  failed: "bg-destructive/10 text-destructive",
  deleted: "bg-muted text-muted-foreground",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileTypeIcon({ docType }: { docType: string }) {
  const label = DOC_TYPE_LABELS[docType] ?? docType.toUpperCase();
  const tone = DOC_TYPE_TONE[docType] ?? "border-muted bg-muted text-muted-foreground";
  return (
    <span
      className={`inline-flex h-8 w-7 shrink-0 flex-col items-center justify-center rounded-md border ${tone}`}
    >
      <FileText className="h-3.5 w-3.5" />
      <span className="text-[7px] font-bold uppercase leading-none">{label}</span>
    </span>
  );
}

function SafetyManagementPage() {
  return (
    <AuthGuard>
      <SafetyManagementContent />
    </AuthGuard>
  );
}

function SafetyManagementContent() {
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const queryClient = useQueryClient();

  // Fetch documents from backend
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["documents", page],
    queryFn: () => fetchDocuments({ page, size: 50 }),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast.success("Document deleted");
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to delete document");
    },
  });

  const documents = data?.data ?? [];

  // Client-side search
  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return documents;
    return documents.filter(
      (doc) =>
        doc.title.toLowerCase().includes(q) ||
        doc.filename.toLowerCase().includes(q),
    );
  }, [searchQuery, documents]);

  const handleDelete = (doc: DocumentResponse) => {
    if (window.confirm(`Delete "${doc.title}"? This action cannot be undone.`)) {
      deleteMutation.mutate(doc.id);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />

      <main className="mx-auto max-w-[1560px] px-6 py-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Safety Management</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Manage approved safety documents and knowledge base used by the AI system for recommendations.
            </p>
          </div>
          <button
            onClick={() => setShowUploadDialog(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            <UploadCloud className="h-4 w-4" />
            Upload Safety Document
          </button>
        </div>

        <section className="mt-6 rounded-xl border border-border bg-card">
          <div className="p-5">
            <div className="relative max-w-lg">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search documents by name or keyword..."
                className="w-full rounded-lg border border-border bg-background py-2.5 pl-10 pr-3 text-sm outline-none focus:border-primary"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            {isLoading ? (
              <div className="flex items-center justify-center py-24">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : isError ? (
              <div className="px-6 py-24 text-center text-sm text-destructive">
                {error instanceof Error ? error.message : "Failed to load documents"}
              </div>
            ) : (
              <table className="w-full min-w-[900px] border-collapse text-sm">
                <thead>
                  <tr className="border-y border-border bg-muted/40 text-left">
                    {[
                      "Type",
                      "Document Title",
                      "Filename",
                      "Size",
                      "Chunks",
                      "Uploaded On",
                      "Status",
                      "Actions",
                    ].map((label) => (
                      <th key={label} className="px-4 py-3 text-xs font-semibold text-foreground">
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((doc) => (
                    <tr key={doc.id} className="border-b border-border last:border-0 hover:bg-muted/30">
                      <td className="px-4 py-4">
                        <FileTypeIcon docType={doc.document_type} />
                      </td>
                      <td className="px-4 py-4 max-w-[280px]">
                        <p className="font-medium">{doc.title}</p>
                        {doc.description && (
                          <p className="mt-0.5 text-xs text-muted-foreground truncate">{doc.description}</p>
                        )}
                      </td>
                      <td className="px-4 py-4 text-muted-foreground">{doc.filename}</td>
                      <td className="px-4 py-4 text-muted-foreground">{formatFileSize(doc.file_size)}</td>
                      <td className="px-4 py-4 text-muted-foreground">{doc.chunk_count}</td>
                      <td className="px-4 py-4">
                        <div className="font-medium">{formatDate(doc.created_at)}</div>
                        <div className="text-xs text-muted-foreground">{formatTime(doc.created_at)}</div>
                      </td>
                      <td className="px-4 py-4">
                        <span
                          className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${DOC_STATUS_TONE[doc.status] ?? "bg-muted text-muted-foreground"}`}
                        >
                          {DOC_STATUS_LABELS[doc.status] ?? doc.status}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <button
                          aria-label={`Delete ${doc.title}`}
                          onClick={() => handleDelete(doc)}
                          disabled={deleteMutation.isPending}
                          className="rounded-md p-2 text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-sm text-muted-foreground">
                        {documents.length === 0 ? "No documents uploaded yet." : "No documents match your search."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
            <p className="text-sm text-muted-foreground">
              Total: {data?.total ?? 0} documents
            </p>
            {data && data.total > data.size && (
              <div className="flex items-center gap-2">
                <button
                  aria-label="Previous page"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="rounded-md border border-border p-2 text-muted-foreground disabled:opacity-50"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="rounded-md border border-primary px-3 py-1.5 text-sm font-semibold text-primary">
                  {page}
                </span>
                <button
                  aria-label="Next page"
                  disabled={page * data.size >= data.total}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-md border border-border p-2 text-muted-foreground disabled:opacity-50"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        </section>
      </main>

      {/* Upload Dialog */}
      {showUploadDialog && (
        <UploadDialog onClose={() => setShowUploadDialog(false)} />
      )}
    </div>
  );
}

function UploadDialog({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!file || !title.trim()) throw new Error("File and title are required");
      return uploadDocument(file, title.trim(), description.trim() || undefined);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast.success("Document uploaded and ingested successfully");
      onClose();
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    uploadMutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">Upload Safety Document</h2>
          <button onClick={onClose} className="rounded-md p-1 text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-sm font-medium">Document Title *</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., PPE Usage Policy"
              required
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium">Description (optional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of this document"
              rows={2}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium">File (.txt, .md, .pdf) *</label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md,.pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
              className="mt-1 w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-primary/10 file:px-3 file:py-2 file:text-sm file:font-medium file:text-primary"
            />
            {file && (
              <p className="mt-1 text-xs text-muted-foreground">
                {file.name} ({formatFileSize(file.size)})
              </p>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium transition-colors hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={uploadMutation.isPending || !file || !title.trim()}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {uploadMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Uploading…
                </>
              ) : (
                <>
                  <UploadCloud className="h-4 w-4" />
                  Upload
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
