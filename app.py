import streamlit as st
import cv2
import numpy as np
import os
import time
import mediapipe as mp
import tensorflow as tf
import warnings
warnings.filterwarnings('ignore')

# MP Holistic:
mp_holistic = mp.solutions.holistic # Holistic model
mp_drawing = mp.solutions.drawing_utils # Drawing utilities

def mediapipe_detection(image, model):
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) # COLOR CONVERSION BGR 2 RGB
    image.flags.writeable = False                  # Image is no longer writeable
    results = model.process(image)                 # Make prediction
    image.flags.writeable = True                   # Image is now writeable 
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR) # COLOR COVERSION RGB 2 BGR
    return image, results

def draw_styled_landmarks(image, results):
    # Draw face connections
    mp_drawing.draw_landmarks(image, results.face_landmarks, mp_holistic.FACE_CONNECTIONS, 
                             mp_drawing.DrawingSpec(color=(80,110,10), thickness=1, circle_radius=1), 
                             mp_drawing.DrawingSpec(color=(80,256,121), thickness=1, circle_radius=1)
                             ) 
    # Draw pose connections
    mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS,
                             mp_drawing.DrawingSpec(color=(80,22,10), thickness=2, circle_radius=4), 
                             mp_drawing.DrawingSpec(color=(80,44,121), thickness=2, circle_radius=2)
                             ) 
    # Draw left hand connections
    mp_drawing.draw_landmarks(image, results.left_hand_landmarks, mp_holistic.HAND_CONNECTIONS, 
                             mp_drawing.DrawingSpec(color=(121,22,76), thickness=2, circle_radius=4), 
                             mp_drawing.DrawingSpec(color=(121,44,250), thickness=2, circle_radius=2)
                             ) 
    # Draw right hand connections  
    mp_drawing.draw_landmarks(image, results.right_hand_landmarks, mp_holistic.HAND_CONNECTIONS, 
                             mp_drawing.DrawingSpec(color=(245,117,66), thickness=2, circle_radius=4), 
                             mp_drawing.DrawingSpec(color=(245,66,230), thickness=2, circle_radius=2)
                             ) 

# Extract Keypoint values
def extract_keypoints(results):
    pose = np.array([[res.x, res.y, res.z, res.visibility] for res in results.pose_landmarks.landmark]).flatten() if results.pose_landmarks else np.zeros(33*4)
    face = np.array([[res.x, res.y, res.z] for res in results.face_landmarks.landmark]).flatten() if results.face_landmarks else np.zeros(1404)
    lh = np.array([[res.x, res.y, res.z] for res in results.left_hand_landmarks.landmark]).flatten() if results.left_hand_landmarks else np.zeros(21*3)
    rh = np.array([[res.x, res.y, res.z] for res in results.right_hand_landmarks.landmark]).flatten() if results.right_hand_landmarks else np.zeros(21*3)
    return np.concatenate([pose, face, lh, rh])

# Load model:
import zipfile
import tempfile

stream = st.file_uploader('TF.Keras model file (.h5py.zip)', type='zip')
if stream is not None:
  myzipfile = zipfile.ZipFile(stream)
  with tempfile.TemporaryDirectory() as tmp_dir:
    myzipfile.extractall(tmp_dir)
    root_folder = myzipfile.namelist()[0] # e.g. "model.h5py"
    model_dir = os.path.join(tmp_dir, root_folder)
    #st.info(f'trying to load model from tmp dir {model_dir}...')
    model = tf.keras.models.load_model(model_dir)

    model.compile(optimizer='adam',
                  loss='categorical_crossentropy',
                  metrics=['accuracy'])

# Visualize prediction:
def prob_viz(res, actions, input_frame):
    output_frame = input_frame.copy()

    pred_dict = dict(zip(actions, res))
    # sorting for prediction and get top 5
    prediction = sorted(pred_dict.items(), key=lambda x: x[1])[::-1][:5]

    for num, pred in enumerate(prediction):
        text = '{}: {}'.format(pred[0], round(float(pred[1]),4))
        cv2.putText(output_frame, text, (0, 85+num*40), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255,255,255), 2, cv2.LINE_AA) 
    return output_frame

# New detection variables
sequence = []
sentence = []
threshold = 0.9
tts = False
actions = np.array(['Halo', 'Perkenalkan', 'Nama', 'Saya', 'Z', 'A', 'I', 'N'])
label_map = {label:num for num, label in enumerate(actions)}

###############################################################################################
                                            # STREAMLIT #

col1, col2 = st.columns((2,1))
with col1:
    st.title('BISINDO Recognition')
    st.write('by Zain')

with col2:
    st.image('./bisindo-app-icon.png')

# Checkboxes
st.header('Webcam')

col1, col2 = st.columns(2)
with col1:
    show_webcam = st.checkbox('Show webcam')
with col2:
    show_landmarks = st.checkbox('Show landmarks')

# Webcam
FRAME_WINDOW = st.image([])
cap = cv2.VideoCapture(0) # device 1/2

# Mediapipe model 
with mp_holistic.Holistic(min_detection_confidence=0.5, min_tracking_confidence=0.5) as holistic:
    while show_webcam:
        # Read feed
        ret, frame = cap.read()

        # Make detections
        image, results = mediapipe_detection(frame, holistic)
        
        # Draw landmarks
        if show_landmarks:
            draw_styled_landmarks(image, results)
        
        # 2. Prediction logic
        keypoints = extract_keypoints(results)

        sequence.append(keypoints)
        sequence = sequence[-60:]
        
        if len(sequence) == 60:
            res = model.predict(np.expand_dims(sequence, axis=0))[0]

            #3. Viz logic
            if res[np.argmax(res)] > threshold: 
                if len(sentence) > 0: 
                    if actions[np.argmax(res)] != sentence[-1]:
                        # incase the first word is halo:
                        if (sentence[0] == '') and (actions[np.argmax(res)] == 'Halo'):
                            pass
                        else:
                            sentence.append(actions[np.argmax(res)])
                            tts = True
                else:
                    sentence.append(actions[np.argmax(res)])
                    tts = True

            if len(sentence) > 8: 
                sentence = sentence[-8:]

            # Viz probabilities
            if show_landmarks:
                image = prob_viz(res, actions, image)

            # show result
            cv2.rectangle(image, (0,0), (640, 40), (245, 117, 16), -1)
            cv2.putText(image, ' '.join(sentence), (3,30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        
        # Show to screen
        frameshow = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        FRAME_WINDOW.image(frameshow)

        # Break gracefully
        if cv2.waitKey(10) & 0xFF == ord('q'):
            break
        
    cap.release()
    cv2.destroyAllWindows()

cap.release()
cv2.destroyAllWindows()
