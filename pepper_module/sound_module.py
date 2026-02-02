import json
import os
import re
import shutil
import sys
import time
import threading

from util.Config import *
from util.compress import compress_data

if sys.version_info[0] < 3:
    text_type = unicode  # type: ignore  # noqa: F821
    string_types = basestring  # type: ignore  # noqa: F821
else:
    text_type = str
    string_types = (str, bytes)


class sound_module:
    def  __init__(self, app, socket, length=1):
        self.socket = socket
        self.length = length
        self.audio_recorder = app.session.service("ALAudioRecorder")
        self.tts = app.session.service("ALTextToSpeech")
        self.aup = app.session.service("ALAudioPlayer")
        self.motion = app.session.service("ALMotion")
        self.memory = app.session.service("ALMemory")
        # Sound localization services
        # core NAOqi services for audio, movement, and perception
        self.sound_loc = app.session.service("ALSoundLocalization")
        self.sound_loc_id = "PepperSoundModule"
        self.sound_tracking = True
        try:
            self.sound_loc.subscribe(self.sound_loc_id)
        except Exception as e:
            print("[sound_module] Failed to subscribe sound localization:", e)
            self.sound_tracking = False
        # Face and people perception services
        self.face_detection = app.session.service("ALFaceDetection")
        self.people_perception = app.session.service("ALPeoplePerception")
        try:
            self.photo_capture = app.session.service("ALPhotoCapture")
        except Exception as e:
            print("[sound_module] Failed to acquire photo capture:", e)
            self.photo_capture = None
        self.fileId = self.aup.loadFile("/data/home/nao/pepper/DINGDONG.wav")
        self.count = 0
        self.audio_recorder.stopMicrophonesRecording()
        self.speech_list = []
        self.running = True
        self.face_tracking = False
        self.body_tracking = False
        self.face_subscriber = "PepperFaceTracker"
        self.people_subscriber = "PepperPeopleTracker"
        # External follow mode flag (set by move_module or show_screen)
        self.external_follow_active = False
        try:
            self.face_detection.subscribe(self.face_subscriber)
            self.face_tracking = True
        except Exception as e:
            print("[sound_module] Failed to subscribe face detection:", e)
        try:
            self.people_perception.subscribe(self.people_subscriber)
            self.body_tracking = True
        except Exception as e:
            print("[sound_module] Failed to subscribe people perception:", e)
        self._last_head_yaw = None
        self._last_head_pitch = None
        self._last_face_stamp = None
        self._last_sound_time = 0.0
        self._last_sound_stamp = None
        self._last_body_angle = None
        self._last_tracked_person = None
        self._last_logged_angle = None
        self._last_visible_ids = None
        self._head_face_map = {}
        self._last_face_identifier = None
        self._last_announced_face_identifier = None
        self._last_face_count = 0
        self._last_face_update = 0.0
        self._face_enroll_thread = None
        self._follow_thread = None
        self._follow_stop_event = threading.Event()
        self._face_capture_dir = "/data/home/nao/pepper/face_enrollments"
        if self.sound_tracking:
            self.sound_thread = threading.Thread(target=self._sound_localization_loop, name="SoundLocalizationThread")
            self.sound_thread.daemon = True
            self.sound_thread.start()
        if self.face_tracking:
            self.face_thread = threading.Thread(target=self._face_track_loop, name="FaceTrackingThread")
            self.face_thread.daemon = True
            self.face_thread.start()
        if self.body_tracking:
            self.body_thread = threading.Thread(target=self._body_align_loop, name="BodyAlignThread")
            self.body_thread.daemon = True
            self.body_thread.start()
        # threading.Thread(target=self.run).start()
    # def run(self):
    #     count = 0
    #     now = "/tmp/record" + str(count) + ".wav"
    #     self.audio_recorder.startMicrophonesRecording(now, "wav", 16000, (0, 0, 1, 0))
    #     time.sleep(self.length)
    #     while True:
    #         self.audio_recorder.stopMicrophonesRecording()
    #
    #         last = now
    #         count += 1
    #         now = "/tmp/record" + str(count) + ".wav"
    #         self.audio_recorder.startMicrophonesRecording(now, "wav", 16000, (0, 0, 1, 0))
    #         self.socket.send(compress_data(open(last, "rb").read()))
    #         os.remove(last)
    #         time.sleep(self.length)
    def run(self):
        while True:
            if self.speech_list:
                text=self.speech_list[0]
                self.tts.say(text)
                self.speech_list.pop()
                time.sleep(text.length*0.1)
            time.sleep(0.5)
    def _sound_localization_loop(self):
        """Listen to sound localization events and steer head yaw toward the source."""
        min_confidence = 0.6
        min_interval = 0.4
        idle_sleep = 0.1
        while self.running and self.sound_tracking:
            try:
                data = self.memory.getData("ALSoundLocalization/SoundLocated")
            except Exception as e:
                print("[sound_module] Failed to get sound localization data:", e)
                break
            if not data or len(data) < 2:
                time.sleep(idle_sleep)
                continue
            try:
                timestamp = tuple(data[0])
            except Exception:
                timestamp = None
            if timestamp is None or timestamp == self._last_sound_stamp:
                time.sleep(idle_sleep)
                continue
            self._last_sound_stamp = timestamp
            direction = data[1]
            if not direction or len(direction) < 3:
                time.sleep(idle_sleep)
                continue
            azimuth, elevation, confidence = direction[:3]
            if confidence < min_confidence:
                time.sleep(idle_sleep)
                continue
            #else:
                #print("[sound_module] SoundLocated ts=%s azimuth=%.3f elevation=%.3f conf=%.3f" % (
                #    str(timestamp), azimuth, elevation, confidence))
            now = time.time()
            if now - self._last_sound_time < min_interval:
                time.sleep(idle_sleep)
                continue
            # Skip sound tracking when external follow mode is active
            if self.external_follow_active:
                time.sleep(idle_sleep)
                continue
            target_yaw = max(min(azimuth, 1.5), -1.5)
            try:
                self.motion.setAngles("HeadYaw", target_yaw, 0.2)
                self._last_head_yaw = target_yaw
                self._last_sound_time = now
            except Exception as e:
                print("[sound_module] setAngles failed:", e)
            time.sleep(0.05)
    def _face_track_loop(self):
        """Poll face detection results and align head toward the most confident face."""
        smoothing = 0.6
        idle_sleep = 0.1
        while self.running and self.face_tracking:
            try:
                data = self.memory.getData("FaceDetected")
            except Exception as e:
                print("[sound_module] Failed to get face data:", e)
                break
            if not data or len(data) < 2 or not data[1]:
                self._last_face_count = 0
                time.sleep(idle_sleep)
                continue
            try:
                timestamp = tuple(data[0])
            except Exception:
                timestamp = None
            if timestamp is None or timestamp == self._last_face_stamp:
                time.sleep(idle_sleep)
                continue
            self._last_face_stamp = timestamp
            face_count = len(data[1]) if isinstance(data[1], (list, tuple)) else 0
            face_info = data[1][0]
            shape_info = face_info[0] if face_info else []
            alpha = shape_info[1] if len(shape_info) > 1 else 0.0
            beta = shape_info[2] if len(shape_info) > 2 else 0.0
            #print("[sound_module] FaceDetected ts=%s yaw=%.3f pitch=%.3f" % (
            #    str(timestamp), alpha, beta))
            recognized_name = None
            extra_info = face_info[1] if len(face_info) > 1 else []
            raw_face_identifier = None
            if isinstance(extra_info, (list, tuple)) and len(extra_info) > 2:
                candidate = extra_info[2]
                if isinstance(candidate, string_types):
                    recognized_name = candidate
                elif isinstance(candidate, (list, tuple)) and candidate:
                    # some NAOqi versions return [name, score]
                    possible = candidate[0]
                    if isinstance(possible, string_types):
                        recognized_name = possible
            if isinstance(extra_info, (list, tuple)) and extra_info:
                possible_id = extra_info[0]
                if isinstance(possible_id, string_types):
                    raw_face_identifier = possible_id
            identifier = recognized_name or raw_face_identifier
            if identifier != self._last_announced_face_identifier:
                if identifier:
                    label = recognized_name if recognized_name else identifier
                    print("[sound_module] Recognized face:", label)
                else:
                    print("[sound_module] Recognized face: None")
                self._last_announced_face_identifier = identifier
            if identifier:
                self._last_face_identifier = identifier
                self._last_face_update = time.time()
            else:
                self._last_face_identifier = None
                self._last_face_update = time.time()
            self._last_face_count = face_count
            # Skip face tracking when external follow mode is active
            if self.external_follow_active:
                time.sleep(idle_sleep)
                continue
            target_yaw = max(min(alpha, 1.5), -1.5)
            target_pitch = max(min(beta, 0.5), -0.5)
            if self._last_head_yaw is None:
                filtered_yaw = target_yaw
            else:
                filtered_yaw = smoothing * target_yaw + (1.0 - smoothing) * self._last_head_yaw
            if self._last_head_pitch is None:
                filtered_pitch = target_pitch
            else:
                filtered_pitch = smoothing * target_pitch + (1.0 - smoothing) * self._last_head_pitch
            try:
                self.motion.setAngles(["HeadYaw", "HeadPitch"], [filtered_yaw, filtered_pitch], 0.05)
                self._last_head_yaw = filtered_yaw
                self._last_head_pitch = filtered_pitch
            except Exception as e:
                print("[sound_module] setAngles failed:", e)
            time.sleep(0.1)
    def _body_align_loop(self):
        """Rotate Pepper's base toward the closest visible person."""
        smoothing = 0.5
        idle_sleep = 0.05
        min_rotation_threshold = 0.04
        log_angle_delta = 0.12
        while self.running and self.body_tracking:
            try:
                visible_ids = self.memory.getData("PeoplePerception/VisiblePeopleList")
                # normalize visible ids to a tuple for stable comparison
                if isinstance(visible_ids, (list, tuple)):
                    norm_visible = tuple(visible_ids)
                elif visible_ids is None:
                    norm_visible = ()
                else:
                    # unexpected type (single id?), wrap it
                    try:
                        norm_visible = tuple(visible_ids)
                    except Exception:
                        norm_visible = (visible_ids,)

                # only print when the visible list changed (including empty)
                if norm_visible != self._last_visible_ids:
                    print("[sound_module] Visible IDs:", visible_ids)
                    for pid in norm_visible:
                        if pid is None or pid == -1:
                            continue
                        shirt_color = None
                        shirt_color_hsv = None
                        try:
                            shirt_color = self.memory.getData("PeoplePerception/Person/%d/ShirtColor" % pid)
                        except Exception:
                            pass
                        try:
                            shirt_color_hsv = self.memory.getData("PeoplePerception/Person/%d/ShirtColorHSV" % pid)
                        except Exception:
                            pass
                        if shirt_color or shirt_color_hsv:
                            print("[sound_module] Person %s shirt color=%s hsv=%s" % (
                                str(pid),
                                shirt_color if shirt_color is not None else "unknown",
                                shirt_color_hsv if shirt_color_hsv is not None else "unknown"))
                    self._last_visible_ids = norm_visible
            except Exception as e:
                print("[sound_module] Failed to get people list:", e)
                break
            valid_ids = [pid for pid in norm_visible if pid is not None and pid != -1]
            # remove bindings for IDs no longer visible
            if self._head_face_map:
                current_set = set(valid_ids)
                for bound_pid in list(self._head_face_map.keys()):
                    if bound_pid not in current_set:
                        bound_face = self._head_face_map.pop(bound_pid)
                        print("[sound_module] Unbound person %s from face %s (person lost)" % (
                            str(bound_pid), str(bound_face)))
            # attempt to bind when exactly one head and one face detected
            if len(valid_ids) == 1:
                pid = valid_ids[0]
                now_time = time.time()
                print(self._last_face_count,self._last_face_identifier)
                if (
                    self._last_face_count == 2
                    and self._last_face_identifier
                    and (now_time - self._last_face_update) < 2.0
                ):
                    current_face = self._head_face_map.get(pid)
                    if current_face != self._last_face_identifier:
                        self._head_face_map[pid] = self._last_face_identifier
                        print("[sound_module] Bound person %s to face %s" % (
                            str(pid), str(self._last_face_identifier)))
                        try:
                            printable_map = {str(k): str(v) for k, v in self._head_face_map.items()}
                            print("[sound_module] Head-face map:", printable_map)
                        except Exception:
                            print("[sound_module] Head-face map update failed")
            if not visible_ids:
                if self._last_tracked_person is not None:
                    print("[sound_module] Lost track of person", self._last_tracked_person)
                self._last_tracked_person = None
                self._last_logged_angle = None
                if self._last_body_angle is not None:
                    try:
                        self.motion.stopMove()
                    except Exception:
                        pass
                    self._last_body_angle = None
                time.sleep(idle_sleep)
                continue
            closest_id = None
            closest_distance = float("inf")
            closest_angle = None
            for pid in visible_ids:
                if pid is None or pid == -1:
                    continue
                try:
                    distance = self.memory.getData("PeoplePerception/Person/%d/Distance" % pid)
                    angle = self.memory.getData("PeoplePerception/Person/%d/Angle" % pid)
                except Exception:
                    continue
                if distance is None or angle is None:
                    continue
                if distance < closest_distance:
                    closest_distance = distance
                    closest_angle = angle
                    closest_id = pid
            if closest_id is None:
                if self._last_tracked_person is not None:
                    print("[sound_module] Lost track of person", self._last_tracked_person)
                self._last_tracked_person = None
                self._last_logged_angle = None
                if self._last_body_angle is not None:
                    try:
                        self.motion.stopMove()
                    except Exception:
                        pass
                    self._last_body_angle = None
                time.sleep(idle_sleep)
                continue
            # Skip body alignment when external follow mode is active
            if self.external_follow_active:
                time.sleep(idle_sleep)
                continue
            if self._last_body_angle is None:
                filtered_angle = closest_angle
            else:
                filtered_angle = smoothing * closest_angle + (1.0 - smoothing) * self._last_body_angle
            filtered_angle = max(min(filtered_angle, 1.2), -1.2)
            if abs(filtered_angle) < min_rotation_threshold:
                try:
                    self.motion.stopMove()
                except Exception:
                    pass
            else:
                rotation_speed = max(min(filtered_angle, 0.5), -0.5)
                try:
                    self.motion.moveToward(0.0, 0.0, rotation_speed)
                except Exception as e:
                    print("[sound_module] moveToward failed:", e)
            self._last_body_angle = filtered_angle
            should_log = False
            if closest_id != self._last_tracked_person:
                should_log = True
            elif self._last_logged_angle is None:
                should_log = True
            elif abs(filtered_angle - self._last_logged_angle) > log_angle_delta:
                should_log = True
            if should_log:
                print("[sound_module] Tracking person %s distance=%.2f angle=%.2f filtered=%.2f" % (
                    str(closest_id), closest_distance, closest_angle, filtered_angle))
                self._last_logged_angle = filtered_angle
            self._last_tracked_person = closest_id
            time.sleep(idle_sleep)
        try:
            self.motion.stopMove()
        except Exception:
            pass
    def say(self, data):
        print(data)
        if data[0]=="{":
            data = json.loads(data)
            if data.get("intent") == "enroll":
                name = data["params"].get("name", "")
                if name:
                  self.start_face_enrollment(name)
                  print("[sound_module] Registered face for:" + name)
            if data.get("intent") == "forget_name":
                name = data["params"].get("name", "")
                if name:
                    self.stop_face_enrollment(name)
                    print("[sound_module] Unregistered face for:" + name)
            if data.get("intent") == "clean_all_name":
                try:
                    learned_faces = self.face_detection.getLearnedFacesList()
                except Exception:
                    learned_faces = []
                if learned_faces:
                    for person_name in learned_faces:
                        try:
                            self.face_detection.forgetPerson(person_name)
                            print("[sound_module] Removed learned face:", person_name)
                        except Exception as cleanup_err:
                            print("[sound_module] Failed to remove face", person_name, cleanup_err)
            if data.get("intent") == "name_list":
                try:
                    learned_faces = self.face_detection.getLearnedFacesList()
                    print("[sound_module] Learned faces:", learned_faces)
                except Exception as e:
                    print("[sound_module] Failed to get learned faces:", e)
            if data.get("intent") == "follow_me":
                name = data["params"].get("name", "")
                distance = data["params"].get("distance", 300)
                if name:
                    # find the person ID associated with the name
                    target_id = None
                    for pid, face_id in self._head_face_map.items():
                        if face_id == name:
                            target_id = pid
                            break
                    if target_id is not None:
                        print("[sound_module] Now following", name, "at distance", distance, "cm")
                        self._follow_person(target_id, distance)
                    else:
                        print("[sound_module] Cannot follow", name, "- not currently visible")

        if data == u'DINGDONG':
            if self.count:
                self.aup.play(self.fileId)
                self.count = 0
            else:
                self.count = 1
            return
        if not isinstance(data, string_types):
            return
        if data[:5] != "SOUND":
            return
        self.tts.say(data[5:])

         #text = data.decode('utf-8')
            #json_str = data.decode('utf-8')
            #print(json_str)
            #if json_str == "DINGDONG":
            #    file_path = "/data/home/nao/pepper/DINGDONG.wav"
            #    self.aup.post.playFile(file_path)
            # command = json.loads(data.decode('utf-8'))
            # print(command)
            # intent = command.get("intent")
            # params = command.get("params", {})
            # if intent == "speak":
            #     context = params[0]
            #     self.speech_list.append(context)
            # #     angle = slots.get("angle", 45)
            # #     self.actions.append(("rwave", angle))
            # # elif intent == "finger_action":
            # #     self.actions.append(("rfinger", None))
    def stop(self):
        self.running = False
        if self._follow_thread and self._follow_thread.is_alive():
            self._follow_stop_event.set()
            self._follow_thread.join(timeout=1.0)
        self._follow_thread = None
        self._follow_stop_event.clear()
        if self.sound_tracking:
            try:
                self.sound_loc.unsubscribe(self.sound_loc_id)
            except Exception:
                pass
            self.sound_tracking = False
        if hasattr(self, "sound_thread") and self.sound_thread.is_alive():
            self.sound_thread.join(timeout=1.0)
        if self.body_tracking:
            try:
                self.people_perception.unsubscribe(self.people_subscriber)
            except Exception:
                pass
            try:
                self.motion.stopMove()
            except Exception:
                pass
            self.body_tracking = False
        if hasattr(self, "body_thread") and self.body_thread.is_alive():
            self.body_thread.join(timeout=1.0)
        if self.face_tracking:
            try:
                self.memory.removeData("FaceDetected")
            except Exception:
                pass
            try:
                self.face_detection.unsubscribe(self.face_subscriber)
            except Exception:
                pass
            self.face_tracking = False
        if hasattr(self, "face_thread") and self.face_thread.is_alive():
            self.face_thread.join(timeout=1.0)
    def __del__(self):
        self.audio_recorder.stopMicrophonesRecording()
        self.running = False
        if self._follow_thread and self._follow_thread.is_alive():
            self._follow_stop_event.set()
            self._follow_thread.join(timeout=1.0)
        self._follow_thread = None
        self._follow_stop_event.clear()
        if self.sound_tracking:
            try:
                self.sound_loc.unsubscribe(self.sound_loc_id)
            except Exception:
                pass
        if self.body_tracking:
            try:
                self.people_perception.unsubscribe(self.people_subscriber)
            except Exception:
                pass
            try:
                self.motion.stopMove()
            except Exception:
                pass
        if self.face_tracking:
            try:
                self.face_detection.unsubscribe(self.face_subscriber)
            except Exception:
                pass
        # remove any faces learned during this session
        try:
            learned_faces = self.face_detection.getLearnedFacesList()
        except Exception:
            learned_faces = []
        if learned_faces:
            for person_name in learned_faces:
                try:
                    self.face_detection.forgetPerson(person_name)
                    print("[sound_module] Removed learned face:", person_name)
                except Exception as cleanup_err:
                    print("[sound_module] Failed to remove face", person_name, cleanup_err)
    def start_face_enrollment(self, person_name):
        if not person_name:
            return
        if self._face_enroll_thread and self._face_enroll_thread.is_alive():
            print("[sound_module] Face enrollment already running")
            return
        self._face_enroll_thread = threading.Thread(
            target=self._face_enroll_worker,
            args=(person_name,),
            name="FaceEnrollThread"
        )
        self._face_enroll_thread.daemon = True
        self._face_enroll_thread.start()
    def _face_enroll_worker(self, person_name):
        print("[sound_module] Face enrollment start for", person_name)
        picture_path = None
        if self.photo_capture:
            try:
                # capture the current face into robot storage so we can learn offline
                if not os.path.exists(self._face_capture_dir):
                    os.makedirs(self._face_capture_dir)
                if hasattr(self.photo_capture, "setResolution"):
                    self.photo_capture.setResolution(2)
                if hasattr(self.photo_capture, "setPictureFormat"):
                    self.photo_capture.setPictureFormat("png")
                filename = "face_%s_%d" % (person_name, int(time.time()))
                result = self.photo_capture.takePicture(self._face_capture_dir, filename)
                if isinstance(result, (list, tuple)) and len(result) >= 2:
                    picture_path = os.path.join(result[0], result[1])
                else:
                    picture_path = os.path.join(self._face_capture_dir, filename + ".png")
                print("[sound_module] Face snapshot saved to", picture_path)
                try:
                    dest_path = os.path.join(os.getcwd(), os.path.basename(picture_path))
                    shutil.copyfile(picture_path, dest_path)
                    print("[sound_module] Snapshot copied to", dest_path)
                except Exception as copy_err:
                    print("[sound_module] Snapshot copy failed:", copy_err)
            except Exception as e:
                print("[sound_module] Photo capture failed:", e)
        enrolled = False
        try:
            # prefer photo-based enrollment when a snapshot is available
            if picture_path and hasattr(self.face_detection, "learnFaceWithPicture"):
                try:
                    self.face_detection.learnFaceWithPicture(person_name, picture_path)
                    enrolled = True
                    print("[sound_module] Face enrolled from picture for", person_name)
                except Exception as e:
                    print("[sound_module] learnFaceWithPicture failed:", e)
            if not enrolled and hasattr(self.face_detection, "learnFace"):
                try:
                    self.face_detection.learnFace(person_name)
                    enrolled = True
                    print("[sound_module] Face enrolled live for", person_name)
                except Exception as e:
                    print("[sound_module] learnFace failed:", e)
            if enrolled:
                try:
                    faces = self.face_detection.getLearnedFacesList()
                    print("[sound_module] Learned faces:", faces)
                except Exception:
                    pass
            else:
                print("[sound_module] Face enrollment failed for", person_name)
        finally:
            self._face_enroll_thread = None
    def stop_face_enrollment(self, person_name):
        if not person_name:
            return
        try:
            self.face_detection.forgetPerson(person_name)
            print("[sound_module] Forgot learned face for", person_name)
        except Exception as e:
            print("[sound_module] forgetPerson failed for", person_name, ":", e)

    def _follow_person(self, target_id, distance_cm):
        if target_id is None:
            print("[sound_module] Cannot follow: target id is None")
            return
        if not self.body_tracking:
            print("[sound_module] Cannot follow: body tracking not available")
            return
        try:
            desired_distance = float(distance_cm) / 100.0
        except Exception:
            desired_distance = 0.3
        desired_distance = max(min(desired_distance, 2.0), 0.2)

        def follow_worker():
            idle_sleep = 0.1
            lost_timeout = 2.0
            last_seen = time.time()
            print("[sound_module] Follow routine started for id", target_id)
            try:
                try:
                    self.motion.stopMove()
                except Exception:
                    pass
                while self.running and not self._follow_stop_event.is_set():
                    try:
                        visible_ids = self.memory.getData("PeoplePerception/VisiblePeopleList")
                    except Exception:
                        visible_ids = []
                    if isinstance(visible_ids, (list, tuple)):
                        norm_visible = list(visible_ids)
                    elif visible_ids is None:
                        norm_visible = []
                    else:
                        norm_visible = [visible_ids]
                    if target_id in norm_visible:
                        last_seen = time.time()
                    elif time.time() - last_seen > lost_timeout:
                        print("[sound_module] Follow target lost", target_id)
                        break
                    try:
                        distance = self.memory.getData("PeoplePerception/Person/%d/Distance" % target_id)
                        angle = self.memory.getData("PeoplePerception/Person/%d/Angle" % target_id)
                    except Exception:
                        distance = None
                        angle = None
                    if distance is None or angle is None:
                        time.sleep(idle_sleep)
                        continue
                    range_error = distance - desired_distance
                    if abs(range_error) < 0.05:
                        forward_speed = 0.0
                    else:
                        forward_speed = max(min(range_error * 0.8, 0.4), -0.4)
                    if abs(angle) < 0.03:
                        turn_speed = 0.0
                    else:
                        turn_speed = max(min(angle * 0.8, 0.5), -0.5)
                    try:
                        self.motion.moveToward(forward_speed, 0.0, turn_speed)
                    except Exception as move_err:
                        print("[sound_module] moveToward failed during follow:", move_err)
                        break
                    time.sleep(idle_sleep)
            finally:
                try:
                    self.motion.stopMove()
                except Exception:
                    pass
                self._follow_stop_event.clear()
                self._follow_thread = None
                print("[sound_module] Follow routine stopped for id", target_id)

        if self._follow_thread and self._follow_thread.is_alive():
            self._follow_stop_event.set()
            self._follow_thread.join(timeout=1.0)
        self._follow_stop_event.clear()
        self._follow_thread = threading.Thread(target=follow_worker, name="FollowPersonThread")
        self._follow_thread.daemon = True
        self._follow_thread.start()