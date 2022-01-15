"""
Project data onto a network.

Add a plot of predictions?
"""
__date__ = "January 2022"

from bokeh.plotting import curdoc
from bokeh.layouts import column, row
from bokeh.models import Button, PreText, TextInput, MultiSelect, \
        RadioButtonGroup, CheckboxGroup
import numpy as np
import os
from sklearn.metrics import confusion_matrix

import lpne


DEFAULT_FEATURE_DIR = '/Users/jack/Desktop/lpne/test_data/features/'
DEFAULT_LABEL_DIR = '/Users/jack/Desktop/lpne/test_data/labels/'
DEFAULT_SAVE_DIR = '/Users/jack/Desktop/lpne/test_data/projected_labels/'
DEFAULT_MODEL_FN = '/Users/jack/Desktop/lpne/test_data/model_state.npy'

MULTISELECT_HEIGHT = 350
MULTISELECT_WIDTH = 400
LABELS = ["CP SAE", "FA SAE"]

COUNTS = None
FNS = None
PREDICTIONS = None



def project_app(doc):

    radio_button_group = RadioButtonGroup(labels=LABELS, active=0)

    if os.path.exists(DEFAULT_FEATURE_DIR):
        initial_options = _my_listdir(DEFAULT_FEATURE_DIR)
    else:
        initial_options = []

    multi_select = MultiSelect(
            value=[],
            options=initial_options,
            title="Select feature files:",
            height=MULTISELECT_HEIGHT,
            width=MULTISELECT_WIDTH,
    )

    def update_multi_select(new_options, multi_select=multi_select):
        multi_select.options = new_options


    def feature_dir_input_callback(attr, old, new):
        """If the directory exists, populate the file selector."""
        if os.path.exists(new):
            load_dir = new
            if load_dir[-1] == os.path.sep:
                load_dir = load_dir[:-1]
            update_multi_select(_my_listdir(load_dir))
            # Update the save directory too.
            temp = load_dir.split(os.path.sep)[:-1] + ['projected_labels']
            save_dir_in.value = os.path.sep.join(temp)
        else:
            alert_box.text = f"Not a valid directory: {new}"


    model_in = TextInput(
            value=DEFAULT_MODEL_FN,
            title="Enter a model filename (.npy):",
    )

    label_checkbox = CheckboxGroup(
            labels=["Load labels?"],
            active=[0],
    )

    label_dir_in = TextInput(
            value=DEFAULT_LABEL_DIR,
            title="Enter a label directory:",
    )

    feature_dir_in = TextInput(
            value=DEFAULT_FEATURE_DIR,
            title="Enter the feature directory:",
    )
    feature_dir_in.on_change("value", feature_dir_input_callback)

    project_button = Button(label="Project Data", width=150)

    save_button = Button(label="Save Predictions", width=150)

    overwrite_checkbox = CheckboxGroup(
            labels=["Overwrite existing files?"],
            active=[],
    )

    save_dir_in = TextInput(
        value=DEFAULT_SAVE_DIR,
        title="Where should predictions be saved?",
        width=MULTISELECT_WIDTH,
    )

    alert_box = PreText(text="")


    def project_callback():
        global COUNTS, FNS, PREDICTIONS
        if project_button.button_type=="success":
            # Reset
            project_button.button_type="default"
            project_button.label="Project Data"
            COUNTS = None
            FNS = None
            PREDICTIONS = None
            save_button.button_type="default"
            save_button.label="Save Predictions"
            alert_box.text = "Reset"
            return
        # Load the features.
        feature_dir = feature_dir_in.value
        if not os.path.exists(feature_dir):
            project_button.button_type = "warning"
            alert_box.text = "Feature directory doesn't exist!"
            return
        feature_fns = sorted(
                [os.path.join(feature_dir,i) for i in multi_select.value],
        )
        if len(feature_fns) == 0:
            project_button.button_type = "warning"
            alert_box.text = "No feature files selected!"
            return
        if 0 in label_checkbox.active:
            label_dir = label_dir_in.value
            if not os.path.exists(label_dir):
                project_button.button_type = "warning"
                alert_box.text = "Label directory doesn't exist!"
                return
            label_fns = []
            for feature_fn in feature_fns:
                label_fn = os.path.join(label_dir, os.path.split(feature_fn)[1])
                if not os.path.exists(label_fn):
                    project_button.button_type = "warning"
                    alert_box.text = f"Label file doesn't exist: {label_fn}!"
                    return
                label_fns.append(label_fn)
            # Load the features and labels.
            features, labels, rois, counts = lpne.load_features_and_labels(
                    feature_fns,
                    label_fns,
                    return_counts=True,
            )
        else:
            # Just load the features.
            features, rois, counts = \
                    lpne.load_features(feature_fns, return_counts=True)
        # Normalize the power features.
        features = lpne.normalize_features(features, mode='std')
        # Load the model.
        if not os.path.exists(model_in.value):
            project_button.button_type = "warning"
            alert_box.text = "Model file doesn't exist!"
            return
        if radio_button_group.active == 0:
            features = lpne.unsqueeze_triangular_array(features, 1)
            features = np.transpose(features, [0,3,1,2])
            model = lpne.CpSae()
        else:
            features = features.reshape(len(features), -1)
            model = lpne.FaSae()
        try:
            model.load_state(model_in.value)
        except (TypeError, ValueError):
            project_button.button_type = "warning"
            alert_box.text = "Incorrect model type!"
            return

        # Make predictions and print message.
        predictions = model.predict(features)
        COUNTS = counts
        FNS = feature_fns
        PREDICTIONS = predictions
        if 0 in label_checkbox.active:
            # Confusion matrix
            confusion = confusion_matrix(labels, predictions)
            # Filter out ignored classes.
            idx = [i for i in range(len(labels)) if labels[i] in model.classes_]
            idx = np.array(idx)
            # Calculate a weighted accuracy.
            acc = model.score(features[idx], labels[idx])
            message = f"Confusion matrix (rows are true labels, columns are " \
                      f"predicted labels):\n{confusion}\n\n" \
                      f"Weighted accuracy: {acc}"
        else:
            pred_vals, pred_counts = np.unique(predictions, return_counts=True)
            message = f"Predictions: {pred_vals}\n" \
                      f"Counts: {pred_counts}"

        project_button.label = "Projected (click to reset)"
        project_button.button_type="success"
        alert_box.text = message

    project_button.on_click(project_callback)


    def save_callback():
        global COUNTS, FNS, PREDICTIONS
        if COUNTS is None or FNS is None or PREDICTIONS is None:
            save_button.button_type="warning"
            alert_box.text = "Data needs to be projected before " \
                             "predictions can be saved!"
            return
        save_dir = save_dir_in.value
        if not os.path.exists(save_dir):
            save_button.button_type="warning"
            alert_box.text = f"Save directory doesn't exist: {save_dir}"
            return
        overwrite = 0 in overwrite_checkbox.active
        counts = np.array(COUNTS)
        assert np.min(counts) > 0
        assert len(counts) == len(FNS)
        assert np.sum(counts) == len(PREDICTIONS)
        i = 0
        for fn, count in zip(FNS, counts):
            out_fn = os.path.join(save_dir, os.path.split(fn)[-1])
            if not overwrite and os.path.exists(out_fn):
                save_button.button_type="warning"
                alert_box.text = f"File already exists: {out_fn}"
                return
            lpne.save_labels(PREDICTIONS[i:i+count], out_fn, overwrite=overwrite)
            i += count
        save_button.button_type="success"
        save_button.label="Saved Predictions"
        alert_box.text = "Saved predictions."


    save_button.on_click(save_callback)


    column_1 = column(
            model_in,
            radio_button_group,
            label_checkbox,
            label_dir_in,
            feature_dir_in,
            multi_select,
            project_button,
            alert_box,
    )
    column_2 = column(
            save_dir_in,
            overwrite_checkbox,
            save_button,
    )
    doc.add_root(row(column_1,column_2))


def _my_listdir(dir):
    if dir == '':
        return []
    return sorted([i for i in os.listdir(dir) if not i.startswith('.')])


# Run the app.
project_app(curdoc())


###
