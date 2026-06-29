package edu.penn.rtg.schedulingapp.input.treeGUI.dialog;

import edu.penn.rtg.schedulingapp.SchComponent;
import edu.penn.rtg.schedulingapp.TreeComponent;
import edu.penn.rtg.schedulingapp.input.treeGUI.CartsTree;

/**
 * EditComponentDialog handles the dialog to edit Scheduling Component in the
 * Scheduling Tree
 */
@SuppressWarnings("serial")
public class EditComponentDialog extends AddComponentDialog {

	private void setFieldValue(TreeComponent c)
	{
		SchComponent component=c.getSchCom();
		if (component.getAlgorithm().equals("DM")) {
			schedulerSelect.setSelectedIndex(0);
		} else if (component.getAlgorithm().equals("EDF")) {
			schedulerSelect.setSelectedIndex(1);
		}
		prevName=c.getCompName();
		compName.setText(c.getCompName());
		minPeriod.setText(Double.toString(component.getMinPeriod()));
		maxPeriod.setText(Double.toString(component.getMaxPeriod()));

		criticality.setText(component.getCriticality());
		subType.setText(component.getSubType());
		vmips.setText(component.getVmipsStr());
	}

	public EditComponentDialog(CartsTree parent,
			TreeComponent component,TreeComponent rootCom) {
		super(parent,rootCom);
		//component.printDebug();
		mode="EDIT";
		setFieldValue(component);
		setTitle("Update Component");
		this.repaint();
	}

}
