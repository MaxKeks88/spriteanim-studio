// Sprite Sheet Maker — Unity side.
//
// The app writes the sheet PNG and a request file; this script (installed once
// into Assets/Editor) slices the sheet and builds the AnimationClip through the
// Unity API, so sprite ids are Unity's own and nothing depends on guessed YAML.
//
// Request files: Assets/SpriteAnimStudio/request-*.json
// Re-run by hand: Tools > Sprite Anim Studio > Process Requests
#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace SpriteAnimStudio
{
    [InitializeOnLoad]
    public static class Installer
    {
        const string Root = "Assets/SpriteAnimStudio";

        static Installer()
        {
            EditorApplication.delayCall += ProcessQuiet;
        }

        static void ProcessQuiet()
        {
            try
            {
                if (Directory.Exists(Root) && Directory.GetFiles(Root, "request-*.json").Length > 0) Process();
            }
            catch (Exception error)
            {
                Debug.LogError("[SpriteAnimStudio] " + error);
            }
        }

        [MenuItem("Tools/Sprite Anim Studio/Process Requests")]
        public static void ProcessMenu()
        {
            Process();
        }

        [Serializable]
        public class EventSpec
        {
            public int frame = 1;
            public string function = "";
            public string stringParam = "";
            public int intParam = 0;
            public float floatParam = 0f;
        }

        [Serializable]
        public class Request
        {
            public string sheet = "";
            public string name = "";
            public string anim = "";
            public int fps = 24;
            public bool loop = true;
            public int cols = 1;
            public int rows = 1;
            public int frames = 1;
            public int cellW = 0;
            public int cellH = 0;
            public int stepW = 0;
            public int stepH = 0;
            public int lead = 0;
            public int ppu = 100;
            public bool pixel = true;
            public bool controller = true;
            // Обновление уже существующих ассетов вместо создания новых рядом с листом.
            public string controllerPath = "";
            public string clipPath = "";
            // События анимации: кадр (1..N), имя функции, параметры.
            public EventSpec[] events = new EventSpec[0];
        }

        public static void Process()
        {
            if (!Directory.Exists(Root)) return;
            AssetDatabase.Refresh();
            foreach (var file in Directory.GetFiles(Root, "request-*.json").OrderBy(f => f, StringComparer.Ordinal))
            {
                Request request;
                try
                {
                    request = JsonUtility.FromJson<Request>(File.ReadAllText(file));
                }
                catch (Exception error)
                {
                    Debug.LogError("[SpriteAnimStudio] bad request " + Path.GetFileName(file) + ": " + error.Message);
                    Remove(file);
                    continue;
                }
                try
                {
                    Apply(request);
                    Remove(file);
                }
                catch (Exception error)
                {
                    Debug.LogError("[SpriteAnimStudio] " + request.sheet + ": " + error);
                }
            }
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
        }

        // Unity keeps a .meta for every asset: deleting only the request leaves an
        // orphan .meta and Unity complains on the next import.
        static void Remove(string file)
        {
            try { File.Delete(file); } catch (Exception) { }
            try { if (File.Exists(file + ".meta")) File.Delete(file + ".meta"); } catch (Exception) { }
        }

        static void Apply(Request request)
        {
            var sheet = request.sheet.Replace('\\', '/');
            if (!sheet.StartsWith("Assets/")) throw new Exception("sheet must be under Assets: " + sheet);
            if (!File.Exists(sheet)) throw new Exception("no sheet file: " + sheet);

            AssetDatabase.ImportAsset(sheet, ImportAssetOptions.ForceUpdate);
            var importer = AssetImporter.GetAtPath(sheet) as TextureImporter;
            if (importer == null) throw new Exception("not a texture: " + sheet);

            var probe = new Texture2D(2, 2);
            probe.LoadImage(File.ReadAllBytes(sheet));
            int texW = probe.width, texH = probe.height;
            UnityEngine.Object.DestroyImmediate(probe);

            // The sheet arrives already sliced in its .meta (written by the app),
            // so here only the animation is built.
            var sprites = AssetDatabase.LoadAllAssetsAtPath(sheet).OfType<Sprite>().ToArray();
            if (sprites.Length < 2)
                throw new Exception("sheet has " + sprites.Length + " sprites — the .meta slicing was not picked up; delete " + sheet + ".meta and install again");

            int frames = Math.Max(1, request.frames);

            if (string.IsNullOrEmpty(request.anim)) return;

            var byName = new Dictionary<string, Sprite>();
            foreach (var sprite in AssetDatabase.LoadAllAssetsAtPath(sheet).OfType<Sprite>())
            {
                if (sprite.name.StartsWith(request.name + "_")) byName[sprite.name] = sprite;
            }
            var ordered = new List<Sprite>();
            for (int i = 0; i < frames; i++)
            {
                Sprite sprite;
                if (byName.TryGetValue(request.name + "_" + (i + 1), out sprite)) ordered.Add(sprite);
            }
            if (ordered.Count == 0) throw new Exception("no sprites were sliced in " + sheet);

            string folder = Path.GetDirectoryName(sheet).Replace('\\', '/');
            string clipPath = string.IsNullOrEmpty(request.clipPath)
                ? folder + "/" + request.anim + ".anim"
                : request.clipPath;
            var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(clipPath);
            if (clip == null)
            {
                if (!string.IsNullOrEmpty(request.clipPath))
                    throw new Exception("no clip at " + clipPath);
                clip = new AnimationClip();
                AssetDatabase.CreateAsset(clip, clipPath);
            }
            else
            {
                clip.ClearCurves();
            }

            clip.frameRate = request.fps > 0 ? request.fps : 24;
            float fps = clip.frameRate;
            var keys = new ObjectReferenceKeyframe[ordered.Count];
            for (int i = 0; i < ordered.Count; i++)
            {
                keys[i] = new ObjectReferenceKeyframe { time = i / fps, value = ordered[i] };
            }
            var binding = EditorCurveBinding.PPtrCurve("", typeof(SpriteRenderer), "m_Sprite");
            AnimationUtility.SetObjectReferenceCurve(clip, binding, keys);
            var settings = AnimationUtility.GetAnimationClipSettings(clip);
            settings.loopTime = request.loop;
            AnimationUtility.SetAnimationClipSettings(clip, settings);

            // События анимации: кадр считается с 1, время — (кадр-1)/fps.
            // Клип перезаписывается целиком, поэтому старые события тоже снимаем.
            var clipEvents = new List<AnimationEvent>();
            if (request.events != null)
            {
                foreach (var spec in request.events)
                {
                    if (spec == null || string.IsNullOrEmpty(spec.function)) continue;
                    clipEvents.Add(new AnimationEvent
                    {
                        time = Mathf.Max(0f, (Mathf.Max(1, spec.frame) - 1) / fps),
                        functionName = spec.function,
                        stringParameter = spec.stringParam ?? "",
                        intParameter = spec.intParam,
                        floatParameter = spec.floatParam,
                    });
                }
            }
            AnimationUtility.SetAnimationEvents(clip, clipEvents.ToArray());
            EditorUtility.SetDirty(clip);

            if (request.controller)
            {
                AnimatorController controller;
                if (!string.IsNullOrEmpty(request.controllerPath))
                {
                    controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(request.controllerPath);
                    if (controller == null) throw new Exception("no controller at " + request.controllerPath);
                }
                else
                {
                    string controllerPath = folder + "/" + request.anim + ".controller";
                    controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(controllerPath);
                    if (controller == null) controller = AnimatorController.CreateAnimatorControllerAtPath(controllerPath);
                }
                var machine = controller.layers[0].stateMachine;
                bool fresh = machine.states.Length == 0;
                AnimatorState state = machine.states.Select(entry => entry.state).FirstOrDefault(s => s.name == request.anim);
                if (state == null) state = machine.AddState(request.anim);
                state.motion = clip;
                // Существующий контроллер мог иметь свой дефолтный стейт — не трогаем.
                if (fresh) machine.defaultState = state;
                EditorUtility.SetDirty(controller);
            }

            Debug.Log("[SpriteAnimStudio] " + request.anim + ": " + ordered.Count + " frames, "
                + clipEvents.Count + " events -> " + clipPath);
        }

        // Test hook: prints what actually ended up in the project.
        public static void Verify()
        {
            Process();
            foreach (var sheet in Directory.GetFiles("Assets", "*.png", SearchOption.AllDirectories))
            {
                string path = sheet.Replace('\\', '/');
                var sprites = AssetDatabase.LoadAllAssetsAtPath(path).OfType<Sprite>().OrderBy(s => s.name).ToArray();
                if (sprites.Length < 2) continue;
                Debug.Log("[Verify] sheet " + path + " sprites=" + sprites.Length
                    + " first=" + sprites.First().name + " rect=" + sprites.First().rect);
            }
            foreach (var clipPath in Directory.GetFiles("Assets", "*.anim", SearchOption.AllDirectories))
            {
                string path = clipPath.Replace('\\', '/');
                var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
                if (clip == null) continue;
                foreach (var binding in AnimationUtility.GetObjectReferenceCurveBindings(clip))
                {
                    var curve = AnimationUtility.GetObjectReferenceCurve(clip, binding);
                    Debug.Log("[Verify] clip " + path + " binding=" + binding.propertyName + " target=" + binding.type.Name
                        + " keys=" + (curve == null ? 0 : curve.Length)
                        + " first=" + (curve != null && curve.Length > 0 && curve[0].value != null ? curve[0].value.name : "-")
                        + " loop=" + AnimationUtility.GetAnimationClipSettings(clip).loopTime);
                }
            }
        }
    }
}
#endif
