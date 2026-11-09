type ServiceStatus = { status: string; service: string } | null;

async function getServiceStatus(url: string): Promise<ServiceStatus> {
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as ServiceStatus;
  } catch {
    return null;
  }
}

function StatusIndicator({
  label,
  status,
}: {
  label: string;
  status: ServiceStatus | "running";
}) {
  const isHealthy = status === "running" || status?.status === "healthy";
  return (
    <li className="list-group-item d-flex justify-content-between align-items-center">
      <span>{label}</span>
      <span
        className={`badge ${isHealthy ? "text-bg-success" : "text-bg-secondary"}`}
      >
        {isHealthy ? "Healthy" : "Unavailable"}
      </span>
    </li>
  );
}

export default async function Home() {
  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  const agentUrl = process.env.AGENT_SERVICE_URL ?? "http://localhost:8001";
  const [backendStatus, agentStatus] = await Promise.all([
    getServiceStatus(`${backendUrl}/api/v1/health`),
    getServiceStatus(`${agentUrl}/health`),
  ]);

  return (
    <main className="container py-5">
      <div className="mx-auto" style={{ maxWidth: "42rem" }}>
        <h1 className="mb-2">Okala Agent Assessment</h1>
        <p className="lead">Frontend is running successfully.</p>
        <ul className="list-group shadow-sm">
          <StatusIndicator label="Frontend" status="running" />
          <StatusIndicator label="Backend API" status={backendStatus} />
          <StatusIndicator label="Agent Service" status={agentStatus} />
        </ul>
      </div>
    </main>
  );
}
