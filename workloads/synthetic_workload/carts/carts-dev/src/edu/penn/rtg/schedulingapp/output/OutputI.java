package edu.penn.rtg.schedulingapp.output;

import edu.penn.rtg.schedulingapp.TreeComponent;

/**
 * Interface for output renderer
 */
public interface OutputI {
	/**
	 * Render the output
	 * 
	 * @param comp
	 *            The component and its descendants who have the analysis output
	 * @param algoName
	 *            Algorithm which has been run on comp
	 */
	void displayOutput(TreeComponent comp, String algoName);
	void displayEmpty();
}
