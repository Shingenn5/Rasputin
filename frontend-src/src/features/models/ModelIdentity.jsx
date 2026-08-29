import React from "react";
import { PublisherLogo } from "./PublisherLogo.jsx";

function modelParts(item) {
  const modelId = String(item?.modelId || item?.id || item?.name || "Model");
  const publisher = String(item?.publisher || item?.provider || modelId.split("/")[0] || "Local");
  const modelName = String(item?.name || modelId.split("/").pop() || modelId);
  return { modelId, publisher, modelName };
}

export function ModelIdentity({ item, size = "lg" }) {
  const { modelId, publisher, modelName } = modelParts(item);
  return (
    <div className="model-identity flex min-w-0 items-center gap-3">
      <PublisherLogo item={{ ...item, publisher, modelId }} size={size} />
      <div className="model-identity__copy min-w-0">
        <h3 className="model-identity__name truncate text-base font-semibold text-foreground">{modelName}</h3>
        <div className="model-identity__publisher truncate text-xs text-muted-foreground">{publisher}</div>
        <div className="model-identity__id truncate text-[0.68rem] text-muted-foreground" title={modelId}>{modelId}</div>
      </div>
    </div>
  );
}

export default ModelIdentity;
