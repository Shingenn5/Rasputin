import React from "react";
import { Avatar } from "../../components/Avatar.jsx";

function modelParts(item) {
  const modelId = String(item?.modelId || item?.id || item?.name || "Model");
  const publisher = String(item?.publisher || item?.provider || modelId.split("/")[0] || "Local");
  const modelName = String(item?.name || modelId.split("/").pop() || modelId);
  return { modelId, publisher, modelName };
}

export function ModelIdentity({ item, size = "lg" }) {
  const { modelId, publisher, modelName } = modelParts(item);
  return (
    <div className="flex min-w-0 items-center gap-3">
      <Avatar name={`${publisher}/${modelName}`} kind="model" size={size} title={`${publisher} ${modelName}`} />
      <div className="min-w-0">
        <h3 className="truncate text-base font-semibold text-foreground">{modelName}</h3>
        <div className="truncate text-xs text-muted-foreground">{publisher}</div>
        <div className="truncate text-[0.68rem] text-muted-foreground" title={modelId}>{modelId}</div>
      </div>
    </div>
  );
}

export default ModelIdentity;
