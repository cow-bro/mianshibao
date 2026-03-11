import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col items-center justify-center px-6 py-16">
      <div className="w-full rounded-2xl border border-slate-200/80 bg-white/85 p-10 shadow-lg backdrop-blur">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Mianshibao</p>
        <h1 className="mt-4 text-4xl font-bold text-slate-900">面试宝项目基建已就绪</h1>
        <p className="mt-4 max-w-2xl text-slate-600">
          前后端基础框架、统一响应、全局异常、容器编排与代码规范工具已配置完成。
        </p>
        <div className="mt-8 flex gap-4">
          <Button>开始开发</Button>
          <Button variant="outline">查看文档</Button>
        </div>
      </div>
    </main>
  );
}
