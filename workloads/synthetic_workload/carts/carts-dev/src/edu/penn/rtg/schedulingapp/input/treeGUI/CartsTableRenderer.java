package edu.penn.rtg.schedulingapp.input.treeGUI;


import java.awt.Component;

import javax.swing.Icon;
import javax.swing.ImageIcon;
import javax.swing.JTree;
import javax.swing.tree.DefaultMutableTreeNode;
import javax.swing.tree.DefaultTreeCellRenderer;


import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.output.CompOutputRenderer;
import edu.penn.rtg.schedulingapp.output.ModelRenderer;
import edu.penn.rtg.schedulingapp.output.ProcessedTaskModelRenderer;
import edu.penn.rtg.schedulingapp.output.ResourceModelRenderer;

import edu.penn.rtg.schedulingapp.TreeComponent;

/**
 * CartsTableRenderer is used to customize the appearance of the Tree UI
 */
@SuppressWarnings("serial")
public class CartsTableRenderer extends DefaultTreeCellRenderer {
	Icon compIcon;
	Icon taskIcon;
	Icon processedIcon;
	Icon modelIcon;
	Icon resourceIcon;
	Icon processModelIcon;

	public CartsTableRenderer() {
		compIcon = new ImageIcon("images/comp.gif");
		taskIcon = new ImageIcon("images/task.gif");
		processedIcon = new ImageIcon("images/checkmark.gif");
		modelIcon = new ImageIcon("images/model.png");
		resourceIcon = new ImageIcon("images/res.png");
		processModelIcon = new ImageIcon("images/pro.png");
	}

	/**
	 * Returns the appropriate Icon depending on the state of the component
	 */
	public Component getTreeCellRendererComponent(JTree tree, Object value,
			boolean sel, boolean expanded, boolean leaf, int row,
			boolean hasFocus) {

		super.getTreeCellRendererComponent(tree, value, sel, expanded, leaf,
				row, hasFocus);
		DefaultMutableTreeNode node = (DefaultMutableTreeNode) value;
		if (node instanceof Task) {
			setIcon(taskIcon);
		} else if (node instanceof TreeComponent) {
			TreeComponent comp = (TreeComponent) node;
			if (comp.isProcessed()) {
				setIcon(processedIcon);
			} else {
				setIcon(compIcon);
			}
		} else if (node instanceof CompOutputRenderer) {
			setIcon(compIcon);
		} else if (node instanceof ResourceModelRenderer) {
			setIcon(resourceIcon);
		} else if (node instanceof ProcessedTaskModelRenderer) {
			setIcon(processModelIcon);
		} else if (node instanceof ModelRenderer) {
			setIcon(modelIcon);
		}

		return this;
	}
}
