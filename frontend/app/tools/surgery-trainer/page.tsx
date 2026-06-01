export default function SurgeryTrainerPage() {
  return (
    <main className="h-dvh overflow-hidden bg-[#fff7fb]">
      <iframe
        title="Mouse Stereotaxic Trainer"
        src="/surgery-trainer/index.html"
        className="h-full w-full border-0 bg-white"
        sandbox="allow-scripts allow-same-origin"
      />
    </main>
  );
}
