/**
 * FileSystem — File System Access API 封装
 *
 * 职责：封装浏览器原生文件系统 API，提供统一的目录扫描和文件读取接口。
 * 上层（ProjectService）通过此接口操作文件，不直接依赖 window.showDirectoryPicker。
 */

export interface FileEntry {
  name: string;
  path: string;
  handle: FileSystemFileHandle;
}

export interface IFileSystem {
  /** 弹出目录选择器，返回目录句柄或 null（用户取消） */
  pickDirectory(): Promise<FileSystemDirectoryHandle | null>;

  /**
   * 递归扫描目录，返回匹配扩展名的文件列表
   * @param handle 目录句柄
   * @param extensions 扩展名列表，如 ['.yaml', '.yml']
   */
  scanDirectory(handle: FileSystemDirectoryHandle, extensions: string[]): Promise<FileEntry[]>;

  /** 读取文件内容为文本 */
  readFile(handle: FileSystemFileHandle): Promise<string>;
}

export class BrowserFileSystem implements IFileSystem {
  async pickDirectory(): Promise<FileSystemDirectoryHandle | null> {
    try {
      return await window.showDirectoryPicker();
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        return null;
      }
      throw err;
    }
  }

  async scanDirectory(
    handle: FileSystemDirectoryHandle,
    extensions: string[],
  ): Promise<FileEntry[]> {
    const results: FileEntry[] = [];
    await this._scan(handle, '', extensions, results);
    return results;
  }

  async readFile(handle: FileSystemFileHandle): Promise<string> {
    const file = await handle.getFile();
    return file.text();
  }

  private async _scan(
    dirHandle: FileSystemDirectoryHandle,
    prefix: string,
    extensions: string[],
    results: FileEntry[],
  ): Promise<void> {
    for await (const [name, entryHandle] of dirHandle.entries()) {
      if (entryHandle.kind === 'directory') {
        // Skip hidden directories and library
        if (name.startsWith('.') || name === 'library') continue;
        await this._scan(
          entryHandle as FileSystemDirectoryHandle,
          `${prefix}${name}/`,
          extensions,
          results,
        );
      } else if (entryHandle.kind === 'file') {
        const ext = name.slice(name.lastIndexOf('.')).toLowerCase();
        if (extensions.includes(ext)) {
          results.push({
            name,
            path: `${prefix}${name}`,
            handle: entryHandle as FileSystemFileHandle,
          });
        }
      }
    }
  }
}
