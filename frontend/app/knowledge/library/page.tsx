"use client";

import KnowledgeWorkspace from "../_components/KnowledgeWorkspace";

export default function PersonalLibraryPage() {
  return (
    <KnowledgeWorkspace
      title="个人资料库学习"
      visibility="PRIVATE"
      allowUpload={true}
      backHref="/knowledge"
    />
  );
}
