import { App } from './components/App.ts';

document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('root');
  if (!root) return;
  const app = new App(root);
  app.mount();
});
