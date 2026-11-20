param([string]$Kind = 'folder', [string]$Title = '', [string]$Start = '')
# Sprite Sheet Maker: the Windows picker on top of every window. A folder is
# picked with the modern Explorer dialog (IFileOpenDialog, «pick folders»), a
# program with the usual open-file dialog. The owner is an invisible topmost
# window brought to the front first — a program started in the background is
# not allowed to take the foreground by itself, so the Alt-key trick is used.
# Prints the chosen path (UTF-8) or nothing.
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class Front {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  public static void Take(IntPtr h) { keybd_event(0x12, 0, 0, UIntPtr.Zero); keybd_event(0x12, 0, 2, UIntPtr.Zero); SetForegroundWindow(h); }
}
[ComImport, Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IShellItem {
  void BindToHandler(IntPtr pbc, ref Guid bhid, ref Guid riid, out IntPtr ppv);
  void GetParent(out IShellItem ppsi);
  void GetDisplayName(uint sigdn, [MarshalAs(UnmanagedType.LPWStr)] out string name);
  void GetAttributes(uint mask, out uint attribs);
  void Compare(IShellItem psi, uint hint, out int order);
}
[ComImport, Guid("42f85136-db7e-439c-85f1-e4075d135fc8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IFileDialog {
  [PreserveSig] int Show(IntPtr parent);
  void SetFileTypes(uint count, IntPtr specs);
  void SetFileTypeIndex(uint index);
  void GetFileTypeIndex(out uint index);
  void Advise(IntPtr sink, out uint cookie);
  void Unadvise(uint cookie);
  void SetOptions(uint fos);
  void GetOptions(out uint fos);
  void SetDefaultFolder(IShellItem item);
  void SetFolder(IShellItem item);
  void GetFolder(out IShellItem item);
  void GetCurrentSelection(out IShellItem item);
  void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string name);
  void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string name);
  void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string title);
  void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string text);
  void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string text);
  void GetResult(out IShellItem item);
}
[ComImport, Guid("DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7")] public class FileOpenDialogCom {}
public static class Picker {
  [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
  static extern void SHCreateItemFromParsingName(string path, IntPtr pbc, ref Guid riid, out IShellItem item);
  public static string Folder(IntPtr owner, string title, string start) {
    IFileDialog d = (IFileDialog)new FileOpenDialogCom();
    d.SetOptions(0x20 | 0x40 | 0x800);  // pick folders, file system only, path must exist
    if (!string.IsNullOrEmpty(title)) d.SetTitle(title);
    if (!string.IsNullOrEmpty(start) && System.IO.Directory.Exists(start)) {
      try { Guid g = typeof(IShellItem).GUID; IShellItem s; SHCreateItemFromParsingName(start, IntPtr.Zero, ref g, out s); d.SetFolder(s); } catch {}
    }
    if (d.Show(owner) != 0) return "";
    IShellItem r; d.GetResult(out r);
    string p; r.GetDisplayName(0x80058000, out p);  // SIGDN_FILESYSPATH
    return p;
  }
}
'@
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$owner.FormBorderStyle = 'None'
$owner.Opacity = 0
$owner.StartPosition = 'CenterScreen'
$owner.Size = New-Object System.Drawing.Size(1, 1)
$owner.Show()
[Front]::Take($owner.Handle)
$owner.Activate()
$result = ''
if ($Kind -eq 'exe') {
  $d = New-Object System.Windows.Forms.OpenFileDialog
  $d.Filter = 'Программа (*.exe;*.bat;*.lnk)|*.exe;*.bat;*.lnk|Все файлы (*.*)|*.*'
  $d.Title = $Title
  if ($Start -and (Test-Path -LiteralPath $Start)) { $d.InitialDirectory = $Start }
  if ($d.ShowDialog($owner) -eq 'OK') { $result = $d.FileName }
} else {
  $result = [Picker]::Folder($owner.Handle, $Title, $Start)
}
$owner.Close()
if ($result) { $result }
