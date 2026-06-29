package edu.penn.rtg.schedulingapp.input.treeGUI.dialog;

import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.input.treeGUI.CartsTree;

/**
 * EditTaskDialog handles the dialog to edit Task in the Scheduling Tree
 */
@SuppressWarnings("serial")
public class EditTaskDialog extends AddTaskDialog {

	private void setFieldValue(Task task)
	{
		nameField.setText(task.getTaskName());
		periodField.setText(Integer.toString((int)task.getPeriod()));
		executionField.setText(Double.toString(task.getExecution()));
		deadlineField.setText(Integer.toString((int)task.getDeadline()));
		int cs=(int)task.getCriticalSection();
		if(cs!=0){
			csField.setText(Integer.toString(cs));
		}
		int jitter=(int)task.getJitter();
		if(jitter!=0){
			jitterField.setText(Integer.toString(jitter));
		}
		int offset=(int)task.getOffset();
		if(offset!=0){
			offsetField.setText(Integer.toString(offset));
		}
		double delta_rel = task.getDelta_rel();
		if(delta_rel != 0){
			delta_rel_field.setText(Double.toString(delta_rel));
		}
		double delta_sch = task.getDelta_sch();
		if(delta_sch != 0){
			delta_sch_field.setText(Double.toString(delta_sch));
		}
		double delta_cxs = task.getDelta_cxs();
		if(delta_cxs != 0){
			delta_cxs_field.setText(Double.toString(delta_cxs));
		}
		double delta_crpmd = task.getDelta_crpmd();
		if(delta_crpmd != 0){
			delta_crpmd_field.setText(Double.toString(delta_crpmd));
		}
			
	}

	public EditTaskDialog(CartsTree parent, Task task) {
		super(parent);
		mode="EDIT";
		setFieldValue(task);
		setTitle("Update Task");
		this.repaint();
	}


}
