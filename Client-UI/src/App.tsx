import { ChatKit, useChatKit } from "@openai/chatkit-react";

export default function App() {
  const chatkit = useChatKit({
    api: {
      url: "http://localhost:8000/chatkit",
      domainKey: "local-dev-poc",
      uploadStrategy: { type: "two_phase" }
    },
    composer: {
      attachments: {
        enabled: true,
        accept: {
          'text/plain': ['.txt'],
          'application/pdf': ['.pdf']
        },
        maxCount: 5,
      },
    },
  });

  return (
    <div style={{ height: '100vh', width: '100vw' }}>
      <ChatKit control={chatkit.control} />
    </div>
  );
}