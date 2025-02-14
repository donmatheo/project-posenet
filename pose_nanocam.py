# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import collections
import time
import numpy as np

import cv2

import nanocamera as nano
import os

from pose_engine_nano import PoseEngineNano

from network_tool import UnityNetwork

EDGES = (
    ('nose', 'left eye'),
    ('nose', 'right eye'),
    ('nose', 'left ear'),
    ('nose', 'right ear'),
    ('left ear', 'left eye'),
    ('right ear', 'right eye'),
    ('left eye', 'right eye'),
    ('left shoulder', 'right shoulder'),
    ('left shoulder', 'left elbow'),
    ('left shoulder', 'left hip'),
    ('right shoulder', 'right elbow'),
    ('right shoulder', 'right hip'),
    ('left elbow', 'left wrist'),
    ('right elbow', 'right wrist'),
    ('left hip', 'right hip'),
    ('left hip', 'left knee'),
    ('right hip', 'right knee'),
    ('left knee', 'left ankle'),
    ('right knee', 'right ankle'),
)

def shadow_text(img, x, y, text, font_size=16):
    cv2.putText(img, text, (x+1, y+1),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.putText(img, text, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

def draw_pose(img, pose, src_size, appsink_size, color=(0, 255, 255), threshold=0.2):
    scale_x = src_size[0] / appsink_size[0]
    scale_y = src_size[1] / appsink_size[1]
    xys = {}
    for label, keypoint in pose.keypoints.items():
        if keypoint.score < threshold:
            continue
        # Offset and scale to source coordinate space.
        kp_y = int(scale_y*keypoint.point.y)
        kp_x = int(scale_x*keypoint.point.x)
        xys[label] = (kp_x, kp_y)
        cv2.circle(img, (kp_x, kp_y), 5, color=(
            209, 156, 0), thickness=-1)  # cyan
        cv2.circle(img, (kp_x, kp_y), 6, color=color, thickness=1)

    for a, b in EDGES:
        if a not in xys or b not in xys:
            continue
        ax, ay = xys[a]
        bx, by = xys[b]
        cv2.line(img, (ax, ay), (bx, by), color, 2)


def avg_fps_counter(window_size):
    window = collections.deque(maxlen=window_size)
    prev = time.monotonic()
    yield 0.0  # First fps value.

    while True:
        curr = time.monotonic()
        window.append(curr - prev)
        prev = curr
        yield len(window) / sum(window)


def calculate_differences(pose, last_pose, threshold=0.3):
    if(pose.keypoints):
        dist_sum = 0
        for label, keypoint in pose.keypoints.items():
            if keypoint.score < threshold:
                continue

            # only calculate dist of left wrists and right wrists
            if label == 9 or label == 10:
                last_pose_point = last_pose.keypoints[label]
                point1 = np.array(keypoint.point)
                point2 = np.array(last_pose_point.point)

                # calculating Euclidean distance
                # using linalg.norm()
                dist = np.linalg.norm(point1 - point2)
                dist_sum += dist
    return dist_sum

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--show', help='show pose, needs attached display', action='store_true')
    parser.add_argument('--model', help='.tflite model path.', required=False)
    parser.add_argument('--res', help='Resolution', default='640x480',
                        choices=['480x360', '640x480', '1280x720'])
    parser.add_argument(
        '--videosrc', help='Which video source to use (csi or usb)', default='usb')
    parser.add_argument(
        '--h264', help='Use video/x-h264 input', action='store_true')
    parser.add_argument(
        '--jpeg', help='Use image/jpeg input', action='store_true')
    args = parser.parse_args()

    default_model = 'models/mobilenet/posenet_mobilenet_v1_075_%d_%d_quant_decoder_edgetpu.tflite'
    if args.res == '480x360':
        src_size = (640, 480)
        appsink_size = (480, 360)
        model = args.model or default_model % (353, 481)
    elif args.res == '640x480':
        src_size = (640, 480)
        appsink_size = (640, 480)
        model = args.model or default_model % (481, 641)
    elif args.res == '1280x720':
        src_size = (1280, 720)
        appsink_size = (1280, 720)
        model = args.model or default_model % (721, 1281)

    print('Loading model: ', model)
    engine = PoseEngineNano(model, mirror=False)
    network = UnityNetwork()
    UDP_IP = os.environ['GAME_HOST']
    print('GAME_HOST (IP): ', UDP_IP)
    input_shape = engine.get_input_tensor_shape()
    inference_size = (input_shape[2], input_shape[1])

    n = 0
    sum_process_time = 0
    sum_inference_time = 0
    fps_counter = avg_fps_counter(30)

    pose_history = {}
    camera = 0

    if args.videosrc != 'csi':
        camera = nano.Camera(camera_type=1, device_id=0,
                             width=640, height=480, fps=30)

    else:
        camera = nano.Camera(flip=0, width=640, height=480, fps=60, enforce_fps=True)
    
    if camera.isReady():
        print('Camera is now ready')

    while camera.isReady():
        frame = camera.read()
        img = cv2.resize(frame,
                         dsize=inference_size,
                         interpolation=cv2.INTER_NEAREST)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        start_time = time.monotonic()
        outputs, inference_time = engine.DetectPosesInFrame(img)
        end_time = time.monotonic()

        pose_number = 0
        pose_count = len(outputs);
        dist_sum = 0;
        for pose in outputs:
            pose_number += 1
            #print(pose.score)

            if pose_number in pose_history:
                last_pose = pose_history[pose_number]
            else:
                last_pose = pose
            if pose != last_pose:
                dist_sum += calculate_differences(pose, last_pose)
                if(dist_sum < 10):
                    dist_sum = 0
            pose_history[pose_number] = pose

        network.sendMovementData(dist_sum, pose_count, UDP_IP)

        if args.show:
            n += 1
            sum_process_time += 1000 * (end_time - start_time)
            sum_inference_time += inference_time

            avg_inference_time = sum_inference_time / n
            text_line = 'PoseNet: %.1fms (%.2f fps) TrueFPS: %.2f Nposes %d' % (
                avg_inference_time, 1000 /
                avg_inference_time, next(fps_counter), len(outputs)
            )
            shadow_text(frame, 10, 20, text_line)
            for pose in outputs:
                draw_pose(frame, pose, src_size, appsink_size)

            cv2.imshow('frame', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    camera.release()
    cv2.destroyAllWindows()
    return


if __name__ == '__main__':
    main()
