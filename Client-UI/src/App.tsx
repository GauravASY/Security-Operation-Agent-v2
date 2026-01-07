import { ChatKit, useChatKit } from "@openai/chatkit-react";

export default function App() {
  const chatkit = useChatKit({
    api: {
      url: "http://localhost:8000/chatkit",
      domainKey: "local-dev-poc", // domain keys are optional in dev
    },
  });

  return (
    <div style={{ height: '100vh', width: '100vw' }}>
      <ChatKit control={chatkit.control} />
    </div>
  );
}