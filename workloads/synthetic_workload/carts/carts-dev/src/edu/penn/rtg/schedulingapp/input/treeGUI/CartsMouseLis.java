package edu.penn.rtg.schedulingapp.input.treeGUI;

import java.awt.event.InputEvent;
import java.awt.event.MouseEvent;
import java.awt.event.MouseListener;

import javax.swing.tree.DefaultMutableTreeNode;
import javax.swing.tree.TreePath;

import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.TreeComponent;



public class CartsMouseLis implements MouseListener{
	private DefaultMutableTreeNode[] selectedComponent;
	private CartsTree tree;
	public CartsMouseLis(CartsTree tree) {
		super();
		this.tree = tree;
	}

	private DefaultMutableTreeNode getSelCom(int idx) {
		return  selectedComponent[idx];
	}
	public DefaultMutableTreeNode getSelLastNode() {
		return selectedComponent[getSelLen()-1];
	}
	public TreeComponent getSelLastCom() {
		return (TreeComponent) selectedComponent[getSelLen()-1];
	}
	public Task getSelLastTask() {
		return (Task) selectedComponent[getSelLen()-1];
	}
	public TreeComponent getSelLastLastCom() {
		return (TreeComponent) selectedComponent[getSelLen()-2];
	}
	public int getSelLen() {
		return selectedComponent.length;
	}
	public boolean isSelNull()
	{
		return selectedComponent==null;
	}



	/**
	 * Mouse has been clicked. Find which button was clicked. If it was left
	 * button, then mark the selected component. If it was the right button,
	 * then show the popup menu
	 */
	@Override
	public void mouseClicked(MouseEvent e) {
		if ((e.getModifiers() & InputEvent.BUTTON3_MASK) == InputEvent.BUTTON3_MASK) {
			int selRow = tree.getRowForLocation(e.getX(), e.getY());
			TreePath selPath = tree.getPathForLocation(e.getX(), e.getY());
			if (selRow != -1) {
				selectedComponent = new DefaultMutableTreeNode[selPath
						.getPathCount()];
				for (int i = 0; i < selPath.getPathCount(); i++) {
					selectedComponent[i] = (DefaultMutableTreeNode) selPath
							.getPathComponent(i);
				}

				Object clickedNode = selPath.getLastPathComponent();
				if (clickedNode instanceof TreeComponent) {
					TreeComponent comp = (TreeComponent) clickedNode;
					tree.setSelectionPath(selPath);
					tree.showPopupComponent(e.getComponent(), e.getX(), e.getY(), comp);
				} else {
					Task task = (Task) clickedNode;
					tree.setSelectionPath(selPath);
					tree.showPopupTask(e.getComponent(), e.getX(), e.getY(), task);
				}
			}
		} else if ((e.getModifiers() & InputEvent.BUTTON1_MASK) == InputEvent.BUTTON1_MASK) {
			int selRow = tree.getRowForLocation(e.getX(), e.getY());
			TreePath selPath = tree.getPathForLocation(e.getX(), e.getY());
			if (selRow != -1) {
				selectedComponent = new DefaultMutableTreeNode[selPath
						.getPathCount()];
				for (int i = 0; i < selPath.getPathCount(); i++) {
					selectedComponent[i] = (DefaultMutableTreeNode) selPath
							.getPathComponent(i);
				}
			}
		}
	}

	@Override
	public void mouseEntered(MouseEvent e) {
		// TODO Auto-generated method stub
		
	}

	@Override
	public void mouseExited(MouseEvent e) {
		// TODO Auto-generated method stub
		
	}

	@Override
	public void mousePressed(MouseEvent e) {
		// TODO Auto-generated method stub
		
	}

	@Override
	public void mouseReleased(MouseEvent e) {
		// TODO Auto-generated method stub
		
	}

}
