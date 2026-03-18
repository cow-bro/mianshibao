"use client";

import KnowledgeWorkspace from "../_components/KnowledgeWorkspace";

export default function GeneralKnowledgePage() {
  return (
    <KnowledgeWorkspace
      title="通用知识库学习"
      scope="GENERAL"
      visibility="PUBLIC"
      allowUpload={false}
      backHref="/knowledge"
    />
  );
}
